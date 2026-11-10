# ⚡ ChaosUI Engine
> **Intelligent Front-End Chaos Engineering for Modern Web Applications**  
> *Simulating the "Impatient, Chaotic Customer" (العميل المشاغب والمستعجل) instead of blind Monkey Testing.*

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Playwright](https://img.shields.io/badge/Powered%20By-Playwright-orange.svg)](https://playwright.dev)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

---

## 🎯 الفكرة والفلسفة (Philosophy)

معظم أدوات فحص واجهات المستخدم التقليدية (Monkey Testing) تقوم بنقر عشوائي أعمى على إحداثيات `(x, y)` عشوائية، مما يستهلك وقتاً طويلاً دون فائدة ولا يمثل سلوك المستخدم الحقيقي.

**ChaosUI Engine** يغير هذه المعادلة بالكامل:
بدلاً من العشوائية العمياء، يحاكي محرك ChaosUI سلوك **"العميل المستعجل، الغاضب والمشاغب"**؛ وهو العميل الذي:
1. **ينقر على زر "الدفع" أو "تأكيد الطلب" 5 مرات متتالية** في جزء من الثانية قبل أن يستجيب الزر أو يُعطل (Rage Clicks).
2. **يرسل النموذج بالزر ثم يضغط فجأة على زر Enter** ويكرر النقر بينما لا يزال طلب الـ Network قيد المعالجة (In-Flight Mutation Race Conditions).
3. **يكتب بسرعة، يمسح، ويعيد الإرسال** أثناء إجراء عمليات التحقق من صحة المدخلات (Validation Race Conditions).
4. **يتنقل للخلف وللأمام (Back/Forward) أو يعيد تحميل الصفحة** في لحظة حدوث عمليات غير متزامنة (Async Operations).
5. **يتصفح الصفحة صعوداً وهبوطاً بسرعة جنونية** لاختبار ثبات الـ Lazy-loading والـ Infinite Scroll.

### الهدف الأساسي (Target Detection Invariants):
* ❄️ **تجمد الشاشة (UI Freeze / Main Thread Blocking):** اكتشاف حظر الـ Main Thread لأكثر من 350ms واختناقات الـ JavaScript الطويلة (LongTasks / Frame Jank).
* 🔁 **تكرار إرسال الطلبات (Duplicate Request / Race Conditions):** كشف إرسال طلبات `POST/PUT/PATCH` متعددة لنفس العملية في نافذة زمنية قصيرة لعدم وجود Debounce أو زر معطل.
* 💥 **الانهيارات والشاشات البيضاء (Crashes & White Screen):** رصد أخطاء `TypeError` غير المعالجة، مشاكل الـ React Error Boundaries، والـ Blank DOM.
* ⏳ **الحالات العالقة (Zombie Spinners & Stuck Buttons):** كشف مؤشرات التحميل الدائمة التي لا تختفي وأزرار العمليات المقفلة نهائياً.

---

## 🏗️ Architecture & Modules

```
chaosui-engine/
├── chaosui/
│   ├── core/
│   │   ├── engine.py           # Central orchestrator & browser session manager
│   │   ├── target_finder.py    # Semantic DOM scanner (finding buttons, inputs, submits)
│   │   ├── session.py          # Action history, metrics, and reproduction tracking
│   │   └── models.py           # Dataclasses & Enums (FaultType, Severity, ActionRecord)
│   ├── personas/
│   │   ├── rage_clicker.py     # "المستعجل": Multi-clicks buttons in rapid bursts (<100ms)
│   │   ├── multi_submitter.py  # "مكرر الإرسال": Double submit via click + Enter + click
│   │   ├── form_thrasher.py    # "مخرب النماذج": Types fast, backspaces, edge-case payloads
│   │   ├── nav_frenzy.py       # "المتنقل السريع": Back/forward/reload during in-flight work
│   │   ├── scroll_thrasher.py  # "المتصفح العنيف": Violent scroll oscillations
│   │   └── chaos_monkey.py     # Smart hybrid persona dynamically weighting tactics
│   ├── detectors/
│   │   ├── freeze.py           # LongTask & requestAnimationFrame heartbeat monitor
│   │   ├── duplicate_requests.py # In-flight POST/PUT/PATCH duplicate mutation interceptor
│   │   ├── crashes.py          # JS uncaught errors, console boundaries, 5xx faults, WSOD
│   │   └── stuck_state.py      # Perpetual spinners and permanently locked buttons
│   ├── network/
│   │   └── chaos_proxy.py      # Latency injection, packet drops, transient 500s
│   ├── reporting/
│   │   ├── console.py          # Rich terminal formatter with diagnostic tables
│   │   ├── html_report.py      # Standalone interactive dashboard with screenshots
│   │   └── json_export.py      # Machine-readable JSON for CI/CD pipelines
│   └── demo/
│       ├── app.py              # FastAPI server with vulnerable real-world test cases
│       └── static/index.html   # Playground dashboard showcasing the 4 major bug classes
└── tests/                      # Full test suite (Unit & E2E integration tests)
```

---

## 🚀 Quickstart

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/Aziz582/chaosui-engine.git
cd chaosui-engine

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies and Playwright Chromium
pip install -e .
playwright install chromium
```

---

### 2. Run the Built-in Playground Demo (تجربة عملية فورية)

يتضمن ChaosUI تطبيق ويب تجريبي متكامل يحتوي عمداً على أشهر أخطاء الـ UI الواقعية (Double Submit, UI Freeze, Crash, Zombie Spinner). يمكنك تجربته فوراً بأمر واحد:

```bash
chaosui demo
```

سيبدأ الخادم المحلي على `http://127.0.0.1:8080`، ويشن هجوم الـ Chaos، ويعرض النتائج الملونة والتقارير في ثوانٍ!

---

### 3. Run ChaosUI on your Web App (فحص أي تطبيق ويب)

```bash
# Basic run against localhost or staging
chaosui run http://localhost:3000

# High-intensity test with custom duration and freeze threshold
chaosui run https://staging.myapp.com --duration 45 --actions 60 --intensity high --freeze-threshold 300

# CI/CD Mode: Fail pipeline if critical UI faults are found
chaosui run https://staging.myapp.com --fail-on-critical
```

#### CLI Options:

| Flag | Default | Description |
|---|---|---|
| `--duration, -d` | `30` | أقصى مدة بالثواني لاختبار الفوضى |
| `--actions, -a` | `35` | الحد الأقصى للإجراءات التفاعلية |
| `--intensity, -i` | `high` | شدة الفوضى (`low`, `medium`, `high`, `insane`) |
| `--persona, -P` | `all` | تحديد شخصيات معينة (مثل `--persona rage_clicker`) |
| `--browser, -b` | `chromium` | محرك المتصفح (`chromium`, `firefox`, `webkit`) |
| `--freeze-threshold` | `350` | عتبة تجمد الشاشة بالمللي ثانية (ms) |
| `--duplicate-window` | `2500` | النافذة الزمنية لاكتشاف تكرار الطلبات (ms) |
| `--headless / --no-headless` | `True` | تشغيل المتصفح في الخلفية أو بوضع مرئي |
| `--network-chaos` | `True` | حقن تأخير عشوائي وانقطاعات في الشبكة |
| `--output, -o` | `chaos_reports` | مجلد حفظ التقارير ولقطات الشاشة |
| `--fail-on-critical` | `False` | إنهاء البرنامج بكود `1` في حال وجود أخطاء حرجة |

---

### 4. Inspect Interactive Targets (فحص العناصر التفاعلية)

لمعرفة العناصر التي يتعرف عليها المحرك في صفحتك وتصنيفها دون تنفيذ أي هجوم:

```bash
chaosui inspect https://my-ecommerce-site.com/checkout
```

---

## 🐍 Python API Usage (الاستخدام البرمجي داخل Pytest)

يمكنك دمج ChaosUI كجزء من اختبارات الـ Integration في مشروعك:

```python
import pytest
from chaosui import ChaosConfig, ChaosEngine

@pytest.mark.asyncio
async def test_checkout_resilience_under_chaos():
    config = ChaosConfig(
        target_url="http://localhost:3000/cart",
        max_duration_seconds=15,
        max_actions=20,
        intensity="high",
        freeze_threshold_ms=300,
        duplicate_window_ms=2000,
        headless=True,
    )
    
    engine = ChaosEngine(config)
    report = await engine.run()

    # Invariants verification
    assert report.critical_faults_count == 0, f"Critical faults detected: {report.faults}"
    assert report.metrics["duplicate_requests_detected"] == 0, "Duplicate requests occurred!"
    assert report.metrics["freeze_events"] == 0, "UI freezes occurred!"
```

---

## 📊 Reports & Diagnostic Evidence

عند اكتمال الفحص، يولد ChaosUI:
1. **تقرير طرفية ملون (Rich Terminal Dashboard):** يوضح جدول الحوادث، درجة خطورتها (`CRITICAL`, `HIGH`, `MEDIUM`)، خطوات إعادة الإنتاج خطوة بخطوة.
2. **تقرير HTML تفاعلي متكامل:** لوحة تحكم عصرية تحتوي على إحصائيات الجلسة، تفاصيل الأدلة (Evidence Telemetry)، مسار الأحداث الزمني (Timeline)، وروابط لقطات الشاشة.
3. **تقرير JSON مهيكل:** مناسب للأرشفة، واستخراج البيانات في مسارات الـ CI/CD (GitHub Actions / GitLab CI).
4. **لقطات شاشة فورية (Screenshots):** تُحفظ تلقائياً في لحظة وقوع الخطأ لتوثيق المشكلة بصرياً.

---

## 🧪 Running Test Suite

```bash
pytest tests/ -v
```

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
