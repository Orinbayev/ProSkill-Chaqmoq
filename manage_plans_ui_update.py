import os

path = r'c:\Users\user\Desktop\chaqmoq_academy\accounts\templates\accounts\center_picker.html'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Replace Button
# We use a broader match or exact string if possible.
# Using unique substring "onclick=\"openPlanModal()\""
if 'onclick="openPlanModal()"' in content:
    content = content.replace('onclick="openPlanModal()"', 'onclick="openPlansManager()"')
else:
    print("Button onclick not found!")

if "Tarif Qo'shish" in content:
    content = content.replace("Tarif Qo'shish", "Tariflar")
else:
    print("Button text not found!")


# 2. Replace Modal
# Searching for <!-- PLAN MODAL -->
start_marker = "<!-- PLAN MODAL -->"
end_marker = "<!-- DELETE MODAL -->"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx != -1 and end_idx != -1:
    new_modals = """<!-- PLANS MANAGER MODAL -->
<div id="plansManageModal" class="cm-overlay">
  <div class="cm-modal p-4" style="max-height: 90vh; overflow-y: auto; max-width: 800px;">
    <div class="d-flex justify-content-between align-items-center mb-4 border-bottom border-secondary pb-3">
      <h5 class="text-white m-0">Tariflar Boshqaruvi</h5>
      <button type="button" class="btn-close btn-close-white" onclick="closeModal('plansManageModal')"></button>
    </div>
    
    <div class="d-flex justify-content-end mb-3">
      <button class="btn-primary-action" onclick="openPlanForm()">
        <i class="bi bi-plus-lg me-2"></i> Yangi Tarif
      </button>
    </div>

    <div class="table-responsive">
      <table class="table table-dark table-hover" style="background: transparent;">
        <thead>
          <tr>
            <th>Kod</th>
            <th>Nomi</th>
            <th>Narxi</th>
            <th>Chegirma</th>
            <th>Limitlar (S/G/U)</th>
            <th>Amallar</th>
          </tr>
        </thead>
        <tbody id="plansTableBody">
          <!-- Populated by JS -->
        </tbody>
      </table>
    </div>
  </div>
</div>

<!-- PLAN FORM MODAL (Create/Edit) -->
<div id="planFormModal" class="cm-overlay" style="z-index: 9100;">
  <div class="cm-modal p-4" style="max-height: 90vh; overflow-y: auto; max-width: 600px;">
    <div class="d-flex justify-content-between align-items-center mb-4 border-bottom border-secondary pb-3">
      <h5 class="text-white m-0" id="planFormTitle">Yangi Tarif</h5>
      <button type="button" class="btn-close btn-close-white" onclick="closeModal('planFormModal')"></button>
    </div>
    
    <form id="planForm">
      <input type="hidden" name="id" id="planId">
      <div class="row g-3">
        <div class="col-md-6">
          <label class="form-label">Tarif Kodi (Unique)</label>
          <input type="text" name="code" id="p_code" class="form-control-dark font-monospace text-uppercase" placeholder="GOLD" required>
        </div>
        <div class="col-md-6">
          <label class="form-label">Tarif Nomi</label>
          <input type="text" name="title" id="p_title" class="form-control-dark" placeholder="Gold Plan" required>
        </div>
        
        <div class="col-md-6">
          <label class="form-label">Oylik Narxi (so'm)</label>
          <input type="number" name="monthly_price" id="p_price" class="form-control-dark" placeholder="500000" required>
        </div>

        <div class="col-md-6">
          <label class="form-label">Chegirma (%)</label>
          <input type="number" name="discount_percent" id="p_discount" class="form-control-dark" placeholder="0" min="0" max="100">
        </div>
        
        <div class="col-md-4">
          <label class="form-label">O'quvchi Limiti</label>
          <input type="number" name="max_students" id="p_students" class="form-control-dark" placeholder="100">
        </div>
        <div class="col-md-4">
          <label class="form-label">Guruh Limiti</label>
          <input type="number" name="max_groups" id="p_groups" class="form-control-dark" placeholder="10">
        </div>
        <div class="col-md-4">
          <label class="form-label">Foydalanuvchi Limiti</label>
          <input type="number" name="max_users" id="p_users" class="form-control-dark" placeholder="3">
        </div>
        
        <div class="col-12 mt-3">
           <div class="form-check form-switch">
              <input class="form-check-input" type="checkbox" name="is_popular" id="p_popular" value="true">
              <label class="form-check-label text-white" for="p_popular">Ommabop (Popular Badge)</label>
           </div>
        </div>
        
        <div class="col-12 mt-4 d-flex justify-content-end gap-2">
           <button type="button" class="btn-ghost" onclick="closeModal('planFormModal')">Bekor qilish</button>
           <button type="button" class="btn-primary-action" onclick="submitPlan()">Saqlash</button>
        </div>
      </div>
    </form>
  </div>
</div>

"""
    # Replace content between markers
    content = content[:start_idx] + new_modals + content[end_idx:]
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Files updated successfully.")
else:
    print("Modals markers not found!")
