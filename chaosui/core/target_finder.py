"""
Semantic DOM target finder for ChaosUI Engine.
Discovers interactive elements and classifies them by operational risk.
"""

from __future__ import annotations
import logging
from typing import List
from playwright.async_api import Page
from chaosui.core.models import TargetInfo

logger = logging.getLogger(__name__)

# JS snippet executed in page to extract interactive DOM elements
DOM_SCAN_SCRIPT = """
() => {
    const isVisible = (el) => {
        if (!el) return false;
        const style = window.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
        const rect = el.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0 && rect.top < window.innerHeight * 2 && rect.bottom > -window.innerHeight;
    };

    const escapeIdent = (val) => {
        if (typeof CSS !== 'undefined' && typeof CSS.escape === 'function') {
            return CSS.escape(val);
        }
        return val.replace(/([!"#$%&'()*+,./:;<=>?@[\\]^`{|}~])/g, '\\\\$1');
    };

    const getSelector = (el) => {
        if (el.id) return `#${escapeIdent(el.id)}`;
        const testId = el.getAttribute('data-testid');
        if (testId) return `[data-testid=${JSON.stringify(testId)}]`;
        if (el.name) return `${el.tagName.toLowerCase()}[name=${JSON.stringify(el.name)}]`;

        let path = [];
        let curr = el;
        while (curr && curr.nodeType === Node.ELEMENT_NODE && path.length < 4) {
            let selector = curr.tagName.toLowerCase();
            if (curr.id) {
                path.unshift(`#${escapeIdent(curr.id)}`);
                break;
            }
            if (curr.className && typeof curr.className === 'string') {
                const classes = curr.className
                    .trim()
                    .split(/\\s+/)
                    .filter(c => c && !c.includes(':') && !c.includes('[') && !c.includes('/'));
                if (classes.length > 0) {
                    selector += '.' + classes.slice(0, 2).map(escapeIdent).join('.');
                }
            }
            if (curr.parentElement) {
                const sameTagSiblings = Array.from(curr.parentElement.children).filter(
                    sib => sib.tagName === curr.tagName
                );
                if (sameTagSiblings.length > 1) {
                    const idx = sameTagSiblings.indexOf(curr) + 1;
                    selector += `:nth-of-type(${idx})`;
                }
            }
            path.unshift(selector);
            curr = curr.parentElement;
        }
        return path.join(' > ');
    };

    const submitKeywords = ['submit', 'pay', 'order', 'send', 'save', 'checkout', 'confirm', 'buy', 'transfer', 'login', 'signup', 'دفع', 'شراء', 'إرسال', 'تأكيد', 'حفظ', 'تسجيل'];
    const destructiveKeywords = ['delete', 'remove', 'cancel', 'clear', 'reset', 'حذف', 'إلغاء'];

    const elements = [];
    const candidates = document.querySelectorAll('button, input, select, textarea, [role="button"], a[role="button"], a.btn, [onclick]');

    for (const el of candidates) {
        if (!isVisible(el)) continue;
        if (el.disabled) continue;

        const tagName = el.tagName.toLowerCase();
        const text = (el.innerText || el.value || el.placeholder || '').trim();
        const ariaLabel = el.getAttribute('aria-label') || '';
        const role = el.getAttribute('role') || '';
        const inputType = el.getAttribute('type') || (tagName === 'input' ? 'text' : null);
        const combinedText = `${text} ${ariaLabel} ${el.id} ${el.className}`.toLowerCase();

        const isSubmit = submitKeywords.some(kw => combinedText.includes(kw)) || inputType === 'submit';
        const isDestructive = destructiveKeywords.some(kw => combinedText.includes(kw));

        const rect = el.getBoundingClientRect();

        elements.push({
            selector: getSelector(el),
            tagName: tagName,
            text: text.slice(0, 100),
            ariaLabel: ariaLabel.slice(0, 100),
            role: role,
            inputType: inputType,
            isSubmit: isSubmit,
            isDestructive: isDestructive,
            boundingBox: {
                x: rect.x,
                y: rect.y,
                width: rect.width,
                height: rect.height
            }
        });
    }

    return elements;
}
"""


class TargetFinder:
    """Scans the active browser page to identify high-value targets for chaos testing."""

    @staticmethod
    async def scan_page(page: Page) -> List[TargetInfo]:
        """Scans the page and returns a list of interactive targets."""
        try:
            raw_elements = await page.evaluate(DOM_SCAN_SCRIPT)
            targets = []
            for item in raw_elements:
                targets.append(
                    TargetInfo(
                        selector=item["selector"],
                        tag_name=item["tagName"],
                        text=item.get("text", ""),
                        aria_label=item.get("ariaLabel"),
                        role=item.get("role"),
                        input_type=item.get("inputType"),
                        is_submit=item.get("isSubmit", False),
                        is_destructive=item.get("isDestructive", False),
                        bounding_box=item.get("boundingBox"),
                    )
                )
            return targets
        except Exception as exc:
            logger.debug("DOM evaluate scan failed, using fallback selector scan: %s", exc)
            try:
                buttons = await page.query_selector_all("button, [role='button']")
            except Exception:
                return []
            fallback_targets = []
            for idx, btn in enumerate(buttons[:10]):
                try:
                    txt = await btn.inner_text()
                    fallback_targets.append(
                        TargetInfo(
                            selector=f"button:nth-of-type({idx + 1})",
                            tag_name="button",
                            text=txt.strip(),
                            is_submit=True,
                        )
                    )
                except Exception as inner_exc:
                    logger.debug("Fallback button inspection skipped: %s", inner_exc)
            return fallback_targets

    @staticmethod
    def filter_submit_targets(targets: List[TargetInfo]) -> List[TargetInfo]:
        """Filters targets that look like form submit, checkout, or transactional actions."""
        return [
            t
            for t in targets
            if t.is_submit or (t.tag_name in ("button", "input") and t.input_type == "submit")
        ]

    @staticmethod
    def filter_input_targets(targets: List[TargetInfo]) -> List[TargetInfo]:
        """Filters targets that accept textual or selection input."""
        return [
            t
            for t in targets
            if t.tag_name in ("input", "textarea", "select")
            and t.input_type not in ("submit", "button", "reset", "hidden")
        ]

    @staticmethod
    def filter_buttons(targets: List[TargetInfo]) -> List[TargetInfo]:
        """Filters all clickable buttons and button-like controls."""
        return [
            t
            for t in targets
            if t.tag_name == "button" or t.role == "button" or t.input_type in ("button", "submit")
        ]
