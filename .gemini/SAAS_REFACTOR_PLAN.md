# 🔒 ChaqmoqApp - SaaS Multi-Tenant Refactoring Plan

**Date:** 2026-02-13  
**Objective:** Complete SaaS transformation with enterprise-grade security, UX, and billing

---

## 📋 ROOT CAUSE ANALYSIS

### **A) Markazlarga "Kirish" tugmasi (Security Risk)**
**Root Cause:** `center_picker.html` template has direct "Kirish" (Enter) button that allows unrestricted SuperAdmin access to tenant data without logging
**Files Affected:**
- `accounts/templates/accounts/center_picker.html`
- `accounts/views.py` (center_switch function)

**Risk Level:** 🔴 **CRITICAL** - Violates data isolation principle

---

### **B) Center Cards UI/UX Issues**
**Root Cause:** Template lacks proper data display structure and responsive design
**Files Affected:**
- `accounts/templates/accounts/center_picker.html`
- CSS styling inline/missing

**Missing Data:**
- Director name + email
- Phone, Address
- Plan name + code combined
- Subscription expiry countdown badge
- Student count vs limit (with overflow badge)
- MRR calculation

---

### **C) Delete Confirmation (Poor UX)**
**Root Cause:** Using browser `confirm()` instead of modal, no name verification
**Files Affected:**
- `accounts/templates/accounts/center_picker.html` (JavaScript)
- `accounts/api_superadmin.py` (delete endpoint)

**Issues:**
- Page scrolls after delete
- No transaction name confirmation
- Primitive UI

---

### **D) TemplateDoesNotExist: center_edit.html**
**Root Cause:** View exists but template file missing
**Files Affected:**
- `accounts/templates/accounts/center_edit.html` (**MISSING**)
- `accounts/views_superadmin.py` (center_edit view)

---

### **E) Promo/Plans Pages Return JSON**
**Root Cause:** Views return `JsonResponse` instead of rendering HTML templates
**Files Affected:**
- `accounts/views_platform.py`
- `accounts/templates/accounts/plans_ui.html`
- `accounts/templates/accounts/promos_ui.html`

**Current Behavior:** Menu links open JSON in browser instead of UI

---

### **F) Logout Button Placement**
**Root Cause:** Dual logout locations (sidebar + profile dropdown)
**Files Affected:**
- `templates/partials/sidebar.html`
- `templates/partials/navbar.html` or profile dropdown

**Required:** Single location in profile dropdown only

---

### **G) Login Redirect Loop (ERR_TOO_MANY_REDIRECTS)**
**Root Cause:** Multiple redirect conditions conflicting
**Files Affected:**
- `core/middleware.py` (TenantMiddleware)
- `accounts/views.py` (login view)
- `config/settings.py` (LOGIN_URL)

**Loop Triggers:**
1. Authenticated user accessing `/login/`
2. Subdomain not found → redirect → subdomain not found
3. Session center_id invalid

---

### **H) Expiry Date Calculation Wrong**
**Root Cause:** Timezone-aware comparison, no grace period handling
**Files Affected:**
- `billing/models.py` (CenterSubscription)
- `accounts/models.py` (Center.is_expired)
- Templates displaying expiry

**Issue:** `28.04.2026` marked as "expired" when today is `13.02.2026`

---

### **I) Plan Form - Max Groups Field Unnecessary**
**Root Cause:** Business logic changed, but model/form not updated
**Files Affected:**
- `billing/models.py` (SubscriptionPlan.max_groups)
- `accounts/templates/accounts/plans_ui.html` (form modal)

**Action:** Remove from UI, keep in model for backward compat (nullable)

---

### **J) Plan Select Empty in Center Create**
**Root Cause:** Form not populating choices, or no active plans
**Files Affected:**
- `accounts/forms.py` (CenterCreateForm)
- `accounts/views_superadmin.py` (center_create view)

**Expected:** Dropdown shows `NAME (CODE) - price UZS`

---

### **K) Student Limit Not Enforced**
**Root Cause:** No validation in student creation flow
**Files Affected:**
- `core/views.py` (student create/edit)
- `accounts/forms.py` (AddUserForm)
- `education/views.py` (enrollment create)

**Required Checks:**
1. UI: Disable "Add Student" button if at limit
2. Backend: Raise ValidationError if limit exceeded
3. Atomic transaction to prevent race conditions

---

## 🎯 IMPLEMENTATION TASKS

### **PHASE 1: Security & Data Isolation (P0 - Critical)**

#### Task 1.1: Remove "Kirish" Button
- [ ] Remove all "Enter Center" buttons from `center_picker.html`
- [ ] Add comment explaining why removed
- [ ] Create separate "Impersonate Mode" (future, optional)

#### Task 1.2: Audit All Queries
- [ ] Search codebase for `.objects.all()` without center filter
- [ ] Add `_filter_center()` helper where needed
- [ ] Test: Verify no cross-tenant data leaks

#### Task 1.3: Subdomain 404 Page
- [ ] Create `core/templates/core/center_404.html`
- [ ] Professional design with branding
- [ ] Clear message: "Center not found"
- [ ] Link to root domain

---

### **PHASE 2: UI/UX Improvements (P1 - High)**

#### Task 2.1: Center Picker Redesign
**File:** `accounts/templates/accounts/center_picker.html`

**Features:**
- Modern card grid layout
- Director info badge
- Plan + limits display
- Expiry countdown badge (color-coded)
- Student count with overflow warning
- MRR display
- Actions menu (3-dot) with:
  - ⚙️ Settings & Director
  - ✏️ Edit
  - 📦 Archive
  - 🗑️ Delete

**Actions Safety:**
- Delete icon at bottom (not next to edit)
- Delete requires modal confirmation

#### Task 2.2: Delete Confirmation Modal
**File:** `accounts/templates/accounts/center_picker.html` (inline modal)

**Implementation:**
```html
<div class="modal" id="deleteModal">
  <p>Bu amal qaytarilmaydi!</p>
  <p>Tasdiqlash uchun markaz nomini kiriting: <strong id="deleteName"></strong></p>
  <input type="text" id="deleteConfirmInput" placeholder="Markaz nomi">
  <button disabled id="deleteConfirmBtn">Ha, o'chirish</button>
</div>
```

**Logic:**
- Input value must exactly match center name
- Enable button only when match
- Stay at current scroll position
- Toast notification after success

#### Task 2.3: Center Edit Template
**File:** `accounts/templates/accounts/center_edit.html` (CREATE NEW)

**Extends:** `base.html`  
**Form Fields:**
- Name, Address, Phone
- Plan selection (dynamic)
- Duration (1/3/6/12 months)
- Total payment (auto-calculated)
- Status override

---

### **PHASE 3: Promo & Plans UI (P1)**

#### Task 3.1: Plans UI Template
**File:** `accounts/templates/accounts/plans_ui.html`

**Layout:**
- Table view with columns: Code, Name, Price, Max Students, Max Users, Discount, Popular, Active
- Actions: Edit, Delete
- "Create Plan" button → modal
- Form validation

#### Task 3.2: Promos UI Template
**File:** `accounts/templates/accounts/promos_ui.html`

**Layout:**
- Table: Code, Discount %, Valid From-To, Max Uses, Used Count, Active
- Actions: Edit, Deactivate, Delete
- "Create Promo" modal

#### Task 3.3: Update views_platform.py
- Change `JsonResponse` → `render(request, template, context)`
- Keep API endpoints separate (for JS fetch)

---

### **PHASE 4: Logout & Profile (P2)**

#### Task 4.1: Remove Sidebar Logout
**File:** `templates/partials/sidebar.html`

- Find and remove `<a href="{% url 'logout' %}">` from sidebar-bottom
- Add comment: `<!-- Logout moved to profile dropdown -->`

#### Task 4.2: Ensure Profile Dropdown Consistent
**Files:** `templates/partials/navbar.html` (or wherever profile is)

**Structure:**
```html
<div class="dropdown">
  <a>Profile Icon</a>
  <div class="dropdown-menu">
    <a href="{% url 'accounts:profile' %}">Profilim</a>
    <form method="post" action="{% url 'logout' %}">
      {% csrf_token %}
      <button type="submit">Chiqish</button>
    </form>
  </div>
</div>
```

---

### **PHASE 5: Login Redirect Fix (P0)**

#### Task 5.1: Middleware Logic
**File:** `core/middleware.py`

**Fix:**
1. Check if user is authenticated AND path is `/hisob/login/`
   → Redirect to `LOGIN_REDIRECT_URL`
2. Subdomain not found:
   - SuperAdmin → Global picker
   - Others → 404 page (not redirect)
3. Session center invalid → clear session, don't redirect

#### Task 5.2: Login View
**File:** `accounts/auth_views.py` or Django's default

**Override:**
```python
def login_view(request):
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)
    # ... rest of login logic
```

---

### **PHASE 6: Expiry Calculation Fix (P1)**

#### Task 6.1: CenterSubscription Model
**File:** `billing/models.py`

**Method:**
```python
def is_expired(self) -> bool:
    if not self.expires_at:
        return False
    now = timezone.now()
    return now >= self.expires_at

def days_until_expiry(self) -> int:
    if not self.expires_at:
        return -1  # No expiry
    delta = self.expires_at - timezone.now()
    return max(0, delta.days)
```

#### Task 6.2: Template Filters
**File:** `billing/templatetags/billing_extras.py` (create if needed)

```python
@register.filter
def expiry_badge_class(days_left):
    if days_left <= 0:
        return 'badge-danger'
    elif days_left <= 7:
        return 'badge-warning'
    else:
        return 'badge-success'
```

---

### **PHASE 7: Student Limit Enforcement (P0 - Critical)**

#### Task 7.1: Backend Validation
**File:** `accounts/forms.py`

```python
class AddUserForm(forms.ModelForm):
    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('role') == 'student':
            center = self.center
            if center:
                sub = getattr(center, 'subscription', None)
                if sub:
                    current_count = User.objects.filter(
                        center=center,
                        role='student',
                        is_archived=False
                    ).count()
                    if current_count >= sub.plan.max_students:
                        raise forms.ValidationError(
                            f"Limit to'ldi! Maksimal {sub.plan.max_students} ta o'quvchi."
                        )
        return cleaned_data
```

#### Task 7.2: UI Indication
**File:** Student list view template

```html
{% if student_count >= max_students %}
  <button disabled>
    <i class="fa fa-lock"></i> Limit to'lgan
  </button>
  <p class="text-danger">
    Yangi o'quvchi qo'shish uchun tarifni yangilang.
  </p>
{% else %}
  <a href="{% url 'add_student' %}" class="btn btn-primary">
    + O'quvchi qo'shish
  </a>
{% endif %}
```

#### Task 7.3: Race Condition Prevention
**File:** `core/views.py` (student create view)

```python
from django.db import transaction

@transaction.atomic
def student_create(request):
    # Lock center row to prevent concurrent creates
    center = Center.objects.select_for_update().get(id=request.center.id)
    # ... check limit
    # ... create student
```

---

## 🧪 TESTING REQUIREMENTS

### Test 1: Tenant Isolation
**File:** `tests/test_tenant_isolation.py`

```python
def test_student_not_visible_across_centers():
    center1 = Center.objects.create(name="Center 1")
    center2 = Center.objects.create(name="Center 2")
    
    student1 = User.objects.create(role='student', center=center1)
    
    # Query as center2 context
    students = User.objects.filter(center=center2, role='student')
    assert student1 not in students
```

### Test 2: Expiry Correctness
```python
def test_expiry_calculation():
    sub = CenterSubscription.objects.create(
        expires_at=timezone.now() + timedelta(days=10)
    )
    assert sub.is_expired() == False
    assert sub.days_until_expiry() == 10
```

### Test 3: Student Limit
```python
def test_student_limit_enforced():
    plan = SubscriptionPlan.objects.create(max_students=2)
    center = Center.objects.create(...)
    sub = CenterSubscription.objects.create(center=center, plan=plan)
    
    User.objects.create(center=center, role='student')
    User.objects.create(center=center, role='student')
    
    with pytest.raises(ValidationError):
        User.objects.create(center=center, role='student')
```

### Test 4: Login Redirect Loop
```python
def test_authenticated_user_cannot_access_login():
    client = Client()
    user = User.objects.create_user(...)
    client.force_login(user)
    
    response = client.get('/hisob/login/')
    assert response.status_code == 302  # Redirect
    assert response.url == reverse('core:home')
```

---

## 📁 FILES TO MODIFY/CREATE

### **Create New:**
1. `accounts/templates/accounts/center_edit.html`
2. `core/templates/core/center_404.html`
3. `tests/test_tenant_isolation.py`
4. `tests/test_billing_logic.py`
5. `tests/test_student_limits.py`

### **Modify Existing:**
1. `accounts/templates/accounts/center_picker.html`
2. `accounts/views.py`
3. `accounts/views_platform.py`
4. `accounts/forms.py`
5. `core/middleware.py`
6. `core/views.py`
7. `billing/models.py`
8. `templates/partials/sidebar.html`
9. `config/settings.py` (if needed)

---

## 🎨 UI/UX DESIGN PRINCIPLES

1. **Consistency:** All pages follow same dark theme, typography, spacing
2. **Safety:** Destructive actions (delete) require confirmation + verification
3. **Clarity:** Badge colors convey status instantly (green=active, red=expired, yellow=warning)
4. **Responsiveness:** Mobile-first, works on all devices
5. **Accessibility:** Proper ARIA labels, keyboard navigation

---

## 🚀 DELIVERY ORDER

**Week 1:**
- Phase 1 (Security) ✅
- Phase 5 (Login Fix) ✅
- Phase 7 (Student Limits) ✅

**Week 2:**
- Phase 2 (UI Redesign) ✅
- Phase 3 (Promo/Plans) ✅
- Phase 6 (Expiry Fix) ✅

**Week 3:**
- Phase 4 (Logout) ✅
- Testing ✅
- Documentation ✅

---

## ✔️ DONE CRITERIA

- [ ] No "Kirish" button exists anywhere
- [ ] All queries filtered by center (no global leaks)
- [ ] Delete confirmation modal with name verification
- [ ] `center_edit.html` template created and working
- [ ] Promo/Plans pages render HTML (not JSON)
- [ ] Single logout location (profile dropdown)
- [ ] No login redirect loops
- [ ] Expiry dates calculated correctly (28.04.2026 = not expired)
- [ ] Student limit enforced (UI + backend + race-safe)
- [ ] All tests passing
- [ ] Beautiful, professional SaaS UI

---

**END OF PLAN**
