(function () {
  function transliterate(value) {
    if (!value) return "";
    value = value
      .toLowerCase()
      .replace(/o['`‘’ʼʻ]/g, "o")
      .replace(/g['`‘’ʼʻ]/g, "g")
      .replace(/['`‘’ʼʻ]/g, "");
    const map = {
      a: "a",
      b: "b",
      d: "d",
      e: "e",
      f: "f",
      g: "g",
      h: "h",
      i: "i",
      j: "j",
      k: "k",
      l: "l",
      m: "m",
      n: "n",
      o: "o",
      p: "p",
      q: "q",
      r: "r",
      s: "s",
      t: "t",
      u: "u",
      v: "v",
      x: "x",
      y: "y",
      z: "z",
      "o'": "o",
      "g'": "g",
      sh: "sh",
      ch: "ch",
      "а": "a",
      "б": "b",
      "в": "v",
      "г": "g",
      "д": "d",
      "е": "e",
      "ё": "yo",
      "ж": "j",
      "з": "z",
      "и": "i",
      "й": "y",
      "к": "k",
      "л": "l",
      "м": "m",
      "н": "n",
      "о": "o",
      "п": "p",
      "р": "r",
      "с": "s",
      "т": "t",
      "у": "u",
      "ф": "f",
      "х": "x",
      "ц": "ts",
      "ч": "ch",
      "ш": "sh",
      "щ": "sh",
      "ъ": "",
      "ы": "i",
      "ь": "",
      "э": "e",
      "ю": "yu",
      "я": "ya"
    };

    return value
      .split("")
      .map(function (char) {
        return map[char] || char;
      })
      .join("")
      .replace(/[^a-z0-9]/g, "");
  }

  function replaceGroupId(template, groupId) {
    if (!template || !groupId) return template;
    return template.replace(/0\/?$/, groupId + "/");
  }

  function formatPhoneValue(value) {
    const digits = String(value || "").replace(/\D/g, "").replace(/^998/, "").slice(0, 9);
    const parts = [];
    if (digits.slice(0, 2)) parts.push(digits.slice(0, 2));
    if (digits.slice(2, 5)) parts.push(digits.slice(2, 5));
    if (digits.slice(5, 7)) parts.push(digits.slice(5, 7));
    if (digits.slice(7, 9)) parts.push(digits.slice(7, 9));
    return parts.join(" ");
  }

  function formatPassportValue(value) {
    const clean = String(value || "").toUpperCase().replace(/[^A-Z0-9]/g, "");
    const letters = clean.replace(/[^A-Z]/g, "").slice(0, 2);
    const numbers = clean.replace(/[^0-9]/g, "").slice(0, 7);
    return letters + numbers;
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function initInputFormatting(scope) {
    scope.querySelectorAll("#id_telefon1, #id_telefon2").forEach(function (input) {
      input.setAttribute('placeholder', '90 123-45-67');
      input.setAttribute('maxlength', '12');
      input.setAttribute('inputmode', 'numeric');
      input.setAttribute('autocomplete', 'off');

      function applyPhoneMask() {
        input.value = formatPhoneValue(input.value);
      }

      function schedulePhoneMask() {
        applyPhoneMask();
        requestAnimationFrame(applyPhoneMask);
        [0, 30, 80, 150, 300, 600, 1000, 2000, 4000].forEach(function (delay) {
          setTimeout(applyPhoneMask, delay);
        });
      }

      schedulePhoneMask();
      input.addEventListener("pointerdown", schedulePhoneMask);
      input.addEventListener("click", schedulePhoneMask);
      input.addEventListener("focus", schedulePhoneMask);
      input.addEventListener("input", applyPhoneMask);
      input.addEventListener("change", applyPhoneMask);
      input.addEventListener("paste", function () {
        schedulePhoneMask();
      });
      input.addEventListener("keyup", applyPhoneMask);
      input.addEventListener("blur", function () {
        const digits = input.value.replace(/\D/g, "").replace(/^998/, "");
        input.value = digits ? formatPhoneValue(input.value) : "";
      });
    });

    scope.querySelectorAll("#id_passport_id").forEach(function (input) {
      function applyPassportMask() {
        input.value = formatPassportValue(input.value);
      }

      applyPassportMask();
      input.addEventListener("input", applyPassportMask);
      input.addEventListener("blur", applyPassportMask);
    });

    scope.querySelectorAll("#id_telegram_username, #id_instagram_username").forEach(function (inp) {
      inp.setAttribute('placeholder', '@username');
      inp.addEventListener('input', function() {
        if (this.value && !this.value.startsWith('@')) this.value = '@' + this.value;
      });
      inp.addEventListener('blur', function() {
        if (this.value === '@') this.value = '';
      });
    });
  }

  function initPasswordToggle(scope) {
    scope.querySelectorAll("[data-toggle-password]").forEach(function (button) {
      button.addEventListener("click", function () {
        const wrapper = button.closest(".bq-sdrawer-password");
        const input = wrapper ? wrapper.querySelector("input") : null;
        const icon = button.querySelector("i");
        if (!input) return;

        const showPassword = input.type === "password";
        input.type = showPassword ? "text" : "password";
        if (icon) {
          icon.className = showPassword ? "fa-regular fa-eye-slash" : "fa-regular fa-eye";
        }
      });
    });
  }

  function initCredentialGenerator(scope) {
    const ismInput = scope.querySelector("#id_ism");
    const familyaInput = scope.querySelector("#id_familya");
    const emailInput = scope.querySelector("#id_email");
    const passwordInput = scope.querySelector("#id_password");

    if (!ismInput || !familyaInput || !emailInput || !passwordInput) return;

    function getIdentityParts() {
      const ismPart = transliterate((ismInput.value || "").trim()).slice(0, 10);
      const familyaPart = transliterate((familyaInput.value || "").trim()).slice(0, 12);
      return {
        ismPart: ismPart || "student",
        familyaPart: familyaPart || "user"
      };
    }

    function createEmailValue() {
      const parts = getIdentityParts();
      const randomPart = Math.floor(Math.random() * 900) + 100;
      const localPart = (parts.ismPart + "." + parts.familyaPart).replace(/\.+/g, ".").replace(/^\.+|\.+$/g, "");
      return localPart.slice(0, 24) + randomPart + "@gmail.com";
    }

    function createPasswordValue() {
      const parts = getIdentityParts();
      const firstChunk = parts.ismPart.slice(0, 4);
      const secondChunk = parts.familyaPart.slice(0, 4);
      const randomPart = String(Math.floor(1000 + Math.random() * 9000));
      const prefix = firstChunk ? firstChunk.charAt(0).toUpperCase() + firstChunk.slice(1) : "Stud";
      return prefix + secondChunk + randomPart;
    }

    function fillCredentials() {
      const ism = (ismInput.value || "").trim();
      const familya = (familyaInput.value || "").trim();
      if (!ism || !familya) return;

      if (!emailInput.value) {
        emailInput.value = createEmailValue();
      }

      if (!passwordInput.value) {
        passwordInput.value = createPasswordValue();
      }
    }

    scope.querySelectorAll("[data-generate-email]").forEach(function (button) {
      button.addEventListener("click", function () {
        emailInput.value = createEmailValue();
        emailInput.focus();
      });
    });

    scope.querySelectorAll("[data-generate-password]").forEach(function (button) {
      button.addEventListener("click", function () {
        passwordInput.value = createPasswordValue();
        passwordInput.focus();
      });
    });

    ismInput.addEventListener("blur", fillCredentials);
    familyaInput.addEventListener("blur", fillCredentials);
    fillCredentials();
  }

  function roundMoneyToThousand(value) {
    const amount = Math.round(Number(value || 0));
    if (!amount) return 0;
    const sign = amount >= 0 ? 1 : -1;
    const absolute = Math.abs(amount);
    return sign * Math.floor((absolute + 500) / 1000) * 1000;
  }

  function formatMoney(value) {
    return roundMoneyToThousand(value).toLocaleString("uz-UZ") + " so'm";
  }

  function parseInteger(value, fallback) {
    const parsed = parseInt(value, 10);
    return Number.isNaN(parsed) ? (fallback || 0) : parsed;
  }

  function parseIsoDate(value) {
    if (!value) return null;
    const parts = String(value).split("-");
    if (parts.length !== 3) return null;
    const year = parseInt(parts[0], 10);
    const month = parseInt(parts[1], 10) - 1;
    const day = parseInt(parts[2], 10);
    const parsed = new Date(year, month, day, 12, 0, 0);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }

  function toIsoDate(date) {
    if (!(date instanceof Date) || Number.isNaN(date.getTime())) return "";
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return year + "-" + month + "-" + day;
  }

  function formatDateLabel(value) {
    const date = parseIsoDate(value);
    if (!date) return "";
    const day = String(date.getDate()).padStart(2, "0");
    const month = String(date.getMonth() + 1).padStart(2, "0");
    return day + "." + month + "." + date.getFullYear();
  }

  function normalizeStartDate(value) {
    const requestedDate = parseIsoDate(value);
    if (!requestedDate) {
      return {
        requestedDate: null,
        effectiveDate: null,
        requestedValue: value || "",
        effectiveValue: "",
        adjustmentNote: ""
      };
    }

    const effectiveDate = new Date(requestedDate.getTime());
    let adjustmentNote = "";
    if (effectiveDate.getDay() === 0) {
      effectiveDate.setDate(effectiveDate.getDate() + 1);
      adjustmentNote = "Yakshanba tanlangani uchun hisob " + formatDateLabel(toIsoDate(effectiveDate)) + " dan boshlandi.";
    }

    return {
      requestedDate: requestedDate,
      effectiveDate: effectiveDate,
      requestedValue: toIsoDate(requestedDate),
      effectiveValue: toIsoDate(effectiveDate),
      adjustmentNote: adjustmentNote
    };
  }

  function lessonPatternLabel(pattern) {
    if (pattern === "odd") return "Toq kunlari";
    if (pattern === "even") return "Juft kunlari";
    if (pattern === "daily") return "Har kuni";
    return "Avtomatik";
  }

  function countedWeekdayLabel(pattern) {
    if (pattern === "odd") return "Dushanba, Chorshanba, Juma";
    if (pattern === "even") return "Seshanba, Payshanba, Shanba";
    if (pattern === "daily") return "Dushanba-Shanba";
    return "";
  }

  function detectPatternForDate(value, mode) {
    if (!value) return "";
    if (mode === "daily") return "daily";
    const normalized = normalizeStartDate(value);
    const date = normalized.effectiveDate;
    if (!date) return "";
    return [1, 3, 5].includes(date.getDay()) ? "odd" : "even";
  }

  function lessonDatesForStartDate(value, pattern) {
    const normalized = normalizeStartDate(value);
    const startDate = normalized.effectiveDate;
    if (!startDate) {
      return {
        startDateValue: "",
        adjustmentNote: "",
        dates: [],
        labels: []
      };
    }

    const monthEnd = new Date(startDate.getFullYear(), startDate.getMonth() + 1, 0, 12, 0, 0);
    const allowedWeekdays = pattern === "daily"
      ? [1, 2, 3, 4, 5, 6]
      : pattern === "even"
        ? [2, 4, 6]
        : [1, 3, 5];
    const dates = [];
    for (let cursor = new Date(startDate.getTime()); cursor <= monthEnd; cursor.setDate(cursor.getDate() + 1)) {
      if (allowedWeekdays.indexOf(cursor.getDay()) !== -1) {
        dates.push(new Date(cursor.getTime()));
      }
    }

    return {
      startDateValue: normalized.effectiveValue,
      adjustmentNote: normalized.adjustmentNote,
      dates: dates,
      labels: dates.map(function (date) {
        return formatDateLabel(toIsoDate(date));
      })
    };
  }

  function initGroupAssignments(scope) {
    const form = scope.querySelector("[data-student-drawer-form]");
    const builder = scope.querySelector("[data-group-assignments-builder]");
    const template = form ? form.dataset.groupPriceTemplate : "";
    const groupSelect = scope.querySelector("#id_group");
    const startDateInput = scope.querySelector("#id_group_start_date");
    const patternModeSelect = scope.querySelector("[data-group-assignment-pattern-mode]");
    const priceInput = scope.querySelector("#id_kurs_narhi");
    const teacherPercentInput = scope.querySelector("[data-group-assignment-teacher-percent]");
    const monthlyLessonsInput = scope.querySelector("[data-group-assignment-monthly-lessons]");
    const hiddenAssignmentsInput = scope.querySelector("#id_group_assignments");
    const list = scope.querySelector("[data-group-assignment-list]");
    const addButton = scope.querySelector("[data-add-group-assignment]");
    const errorBox = scope.querySelector("[data-group-assignment-error]");
    const priceNote = scope.querySelector("[data-group-price-note]");

    if (
      !form || !builder || !template || !groupSelect || !startDateInput || !patternModeSelect ||
      !priceInput || !teacherPercentInput || !monthlyLessonsInput || !hiddenAssignmentsInput || !list
    ) {
      return;
    }

    const previewNodes = {
      pattern: builder.querySelector("[data-preview-pattern]"),
      startDate: builder.querySelector("[data-preview-start-date]"),
      lessons: builder.querySelector("[data-preview-lessons]"),
      fee: builder.querySelector("[data-preview-fee]"),
      teacher: builder.querySelector("[data-preview-teacher]"),
      center: builder.querySelector("[data-preview-center]"),
      note: builder.querySelector("[data-preview-note]")
    };
    const state = {
      currentGroupMeta: null
    };

    function readAssignments() {
      try {
        const parsed = JSON.parse(hiddenAssignmentsInput.value || "[]");
        return Array.isArray(parsed) ? parsed : [];
      } catch (_error) {
        return [];
      }
    }

    function writeAssignments(assignments) {
      hiddenAssignmentsInput.value = JSON.stringify(assignments || []);
    }

    function setError(message) {
      if (!errorBox) return;
      errorBox.textContent = message || "";
    }

    function candidateGroupName() {
      const option = groupSelect.options[groupSelect.selectedIndex];
      return option ? option.textContent.trim() : "";
    }

    function buildCandidatePreview() {
      const groupId = groupSelect.value;
      const startDateValue = startDateInput.value;
      const pattern = detectPatternForDate(startDateValue, patternModeSelect.value);
      const lessonMeta = lessonDatesForStartDate(startDateValue, pattern);
      const defaultPrice = state.currentGroupMeta ? parseInteger(state.currentGroupMeta.price, 0) : 0;
      const defaultTeacherPercent = state.currentGroupMeta ? parseInteger(state.currentGroupMeta.oqituvchi_foiz, 40) : 40;
      const monthlyLessons = parseInteger(monthlyLessonsInput.value, state.currentGroupMeta ? state.currentGroupMeta.monthly_lessons : 12);
      const coursePrice = parseInteger(priceInput.value, defaultPrice);
      const teacherPercent = parseInteger(teacherPercentInput.value, defaultTeacherPercent);
      const feeAmount = monthlyLessons > 0 ? Math.round((coursePrice * lessonMeta.dates.length) / monthlyLessons) : 0;
      const teacherShare = Math.round((feeAmount * teacherPercent) / 100);
      const centerShare = feeAmount - teacherShare;
      const isIndividualPrice = defaultPrice > 0 && coursePrice !== defaultPrice;

      return {
        ready: Boolean(groupId && startDateValue),
        group_id: parseInteger(groupId, 0),
        group_name: (state.currentGroupMeta && state.currentGroupMeta.group_name) || candidateGroupName(),
        requested_start_date: startDateValue,
        start_date: lessonMeta.startDateValue,
        lesson_pattern: pattern,
        lesson_pattern_label: lessonPatternLabel(pattern),
        lesson_count: lessonMeta.dates.length,
        lesson_dates: lessonMeta.labels,
        course_price: coursePrice,
        default_course_price: defaultPrice,
        is_individual_price: isIndividualPrice,
        teacher_percent: teacherPercent,
        center_percent: 100 - teacherPercent,
        monthly_lessons: monthlyLessons,
        fee_amount: feeAmount,
        teacher_share: teacherShare,
        center_share: centerShare,
        note: [lessonMeta.adjustmentNote, countedWeekdayLabel(pattern)].filter(Boolean).join(" • ")
      };
    }

    function renderPreview() {
      const preview = buildCandidatePreview();
      if (previewNodes.pattern) previewNodes.pattern.textContent = preview.lesson_pattern_label || "Pattern tanlanmagan";
      if (previewNodes.startDate) previewNodes.startDate.textContent = preview.start_date ? formatDateLabel(preview.start_date) : "Sana tanlanmagan";
      if (previewNodes.lessons) previewNodes.lessons.textContent = preview.lesson_count + " ta";
      if (previewNodes.fee) previewNodes.fee.textContent = formatMoney(preview.fee_amount);
      if (previewNodes.teacher) previewNodes.teacher.textContent = formatMoney(preview.teacher_share);
      if (previewNodes.center) previewNodes.center.textContent = formatMoney(preview.center_share);
      if (previewNodes.note) previewNodes.note.textContent = preview.note || "Guruh va boshlanish sanasi tanlang.";
      if (priceNote) {
        if (preview.default_course_price > 0) {
          priceNote.textContent = preview.is_individual_price
            ? "Standart " + formatMoney(preview.default_course_price) + ", individual " + formatMoney(preview.course_price) + "."
            : "Standart guruh narxi: " + formatMoney(preview.default_course_price) + ".";
        } else {
          priceNote.textContent = "Standart guruh narxi avtomatik qo'yiladi, xohlasangiz individual narx kiriting.";
        }
      }
      return preview;
    }

    function removeAssignment(index) {
      const assignments = readAssignments();
      assignments.splice(index, 1);
      writeAssignments(assignments);
      renderAssignments();
      setError("");
    }

    function renderAssignments() {
      const assignments = readAssignments();
      list.innerHTML = "";

      if (!assignments.length) {
        list.innerHTML = '<div class="bq-sdrawer-card__note">Hali guruh qo\'shilmadi.</div>';
        return;
      }

      assignments.forEach(function (assignment, index) {
        const item = document.createElement("div");
        item.className = "bq-sdrawer-group-item";
        item.innerHTML = [
          '<div class="bq-sdrawer-group-item__head">',
            '<div class="bq-sdrawer-group-item__title">',
              '<strong>' + escapeHtml(assignment.group_name) + '</strong>',
              '<span>' + escapeHtml(assignment.lesson_pattern_label) + ' • ' + escapeHtml(formatDateLabel(assignment.start_date)) + '</span>',
            '</div>',
            '<button type="button" class="bq-sdrawer-group-remove" data-remove-index="' + index + '" aria-label="Guruhni olib tashlash">',
              '<i class="fa-solid fa-trash"></i>',
            '</button>',
          '</div>',
          '<div class="bq-sdrawer-group-item__metrics">',
            '<div><span>Shu oy darslari</span><strong>' + assignment.lesson_count + ' ta</strong></div>',
            '<div><span>Shu oy qarzi</span><strong>' + formatMoney(assignment.fee_amount) + '</strong></div>',
            '<div><span>O\'qituvchi</span><strong>' + formatMoney(assignment.teacher_share) + '</strong></div>',
            '<div><span>Markaz</span><strong>' + formatMoney(assignment.center_share) + '</strong></div>',
          '</div>',
          assignment.lesson_dates && assignment.lesson_dates.length
            ? '<div class="bq-sdrawer-group-dates">' + assignment.lesson_dates.map(function (label) {
                return '<span>' + escapeHtml(label) + '</span>';
              }).join("") + '</div>'
            : "",
          '<div class="bq-sdrawer-group-item__foot">',
            '<span>' + (assignment.is_individual_price
              ? "Individual narx: " + formatMoney(assignment.course_price)
              : "Standart narx: " + formatMoney(assignment.course_price)) + '</span>',
            '<span>Ulush: ' + assignment.teacher_percent + '% / ' + assignment.center_percent + '%</span>',
          '</div>'
        ].join("");
        list.appendChild(item);
      });

      list.querySelectorAll("[data-remove-index]").forEach(function (button) {
        button.addEventListener("click", function () {
          removeAssignment(parseInteger(button.dataset.removeIndex, -1));
        });
      });
    }

    function addCurrentAssignment() {
      const preview = renderPreview();
      if (!preview.group_id) {
        setError("Avval guruh tanlang.");
        return false;
      }
      if (!preview.requested_start_date) {
        setError("Boshlanish sanasini kiriting.");
        return false;
      }

      const assignments = readAssignments();
      if (assignments.some(function (assignment) { return parseInteger(assignment.group_id, 0) === preview.group_id; })) {
        setError("Bu guruh allaqachon qo'shilgan.");
        return false;
      }

      assignments.push(preview);
      writeAssignments(assignments);
      renderAssignments();
      setError("");
      groupSelect.value = "";
      state.currentGroupMeta = null;
      priceInput.value = "";
      teacherPercentInput.value = "40";
      monthlyLessonsInput.value = "12";
      patternModeSelect.value = "auto";
      renderPreview();
      return true;
    }

    function loadGroupMeta() {
      const groupId = groupSelect.value;
      if (!groupId) {
        state.currentGroupMeta = null;
        priceInput.value = "";
        teacherPercentInput.value = "40";
        monthlyLessonsInput.value = "12";
        renderPreview();
        return Promise.resolve();
      }

      return fetch(replaceGroupId(template, groupId), {
        headers: {
          "X-Requested-With": "XMLHttpRequest"
        }
      })
        .then(function (response) {
          if (!response.ok) {
            throw new Error("price-fetch-failed");
          }
          return response.json();
        })
        .then(function (data) {
          state.currentGroupMeta = data || {};
          priceInput.value = String(parseInteger(data.price, 0));
          teacherPercentInput.value = String(parseInteger(data.oqituvchi_foiz, 40));
          monthlyLessonsInput.value = String(parseInteger(data.monthly_lessons, 12));
          renderPreview();
        })
        .catch(function () {
          state.currentGroupMeta = {
            price: priceInput.value || 0,
            oqituvchi_foiz: teacherPercentInput.value || 40,
            monthly_lessons: monthlyLessonsInput.value || 12,
            group_name: candidateGroupName()
          };
          renderPreview();
        });
    }

    groupSelect.addEventListener("change", function () {
      loadGroupMeta();
    });
    startDateInput.addEventListener("change", renderPreview);
    patternModeSelect.addEventListener("change", renderPreview);
    priceInput.addEventListener("input", renderPreview);
    teacherPercentInput.addEventListener("input", renderPreview);
    monthlyLessonsInput.addEventListener("input", renderPreview);

    if (addButton) {
      addButton.addEventListener("click", addCurrentAssignment);
    }

    form.addEventListener("submit", function () {
      if (groupSelect.value && startDateInput.value) {
        addCurrentAssignment();
      }
    });

    renderAssignments();
    loadGroupMeta().finally(function () {
      renderPreview();
    });
  }

  function initExtraFields(scope) {
    function clearField(row) {
      row.querySelectorAll("input, textarea, select").forEach(function (input) {
        if (input.tagName === "SELECT") {
          input.selectedIndex = 0;
          input.dispatchEvent(new Event("change", { bubbles: true }));
          return;
        }

        if (input.type === "checkbox" || input.type === "radio") {
          input.checked = false;
          return;
        }

        input.value = "";
      });
    }

    function setFieldVisibility(fieldName, visible) {
      const row = scope.querySelector('[data-extra-field="' + fieldName + '"]');
      const toggle = scope.querySelector('[data-extra-toggle="' + fieldName + '"]');
      if (!row || !toggle) return;

      row.hidden = !visible;
      toggle.classList.toggle("is-active", visible);
      toggle.setAttribute("aria-pressed", visible ? "true" : "false");

      if (visible) {
        const input = row.querySelector("input, textarea, select");
        if (input) input.focus();
        return;
      }

      clearField(row);
    }

    scope.querySelectorAll("[data-extra-toggle]").forEach(function (button) {
      button.addEventListener("click", function () {
        const fieldName = button.dataset.extraToggle;
        const row = scope.querySelector('[data-extra-field="' + fieldName + '"]');
        const shouldShow = row ? row.hidden : false;
        setFieldVisibility(fieldName, shouldShow);
      });
    });

    scope.querySelectorAll("[data-extra-remove]").forEach(function (button) {
      button.addEventListener("click", function () {
        setFieldVisibility(button.dataset.extraRemove, false);
      });
    });

    scope.querySelectorAll("[data-extra-field]").forEach(function (row) {
      const fieldName = row.dataset.extraField;
      const toggle = scope.querySelector('[data-extra-toggle="' + fieldName + '"]');
      if (!toggle) return;
      const isVisible = !row.hidden;
      toggle.classList.toggle("is-active", isVisible);
      toggle.setAttribute("aria-pressed", isVisible ? "true" : "false");
    });
  }

  function initOptionalSections(scope) {
    function syncSectionToggle(sectionName, visible) {
      const toggle = scope.querySelector('[data-section-toggle="' + sectionName + '"]');
      if (!toggle) return;

      const openLabel = toggle.dataset.openLabel || "Ochish";
      const closeLabel = toggle.dataset.closeLabel || openLabel;
      toggle.classList.toggle("is-active", visible);
      toggle.setAttribute("aria-expanded", visible ? "true" : "false");
      toggle.textContent = visible ? closeLabel : openLabel;
    }

    function setSectionVisibility(sectionName, visible) {
      const section = scope.querySelector('[data-optional-section="' + sectionName + '"]');
      if (!section) return;

      section.hidden = !visible;
      syncSectionToggle(sectionName, visible);

      if (visible) {
        const input = section.querySelector("input, textarea, select");
        if (input) input.focus();
      }
    }

    scope.querySelectorAll("[data-section-toggle]").forEach(function (button) {
      button.addEventListener("click", function () {
        const sectionName = button.dataset.sectionToggle;
        const section = scope.querySelector('[data-optional-section="' + sectionName + '"]');
        const shouldShow = section ? section.hidden : false;
        setSectionVisibility(sectionName, shouldShow);
      });
    });

    scope.querySelectorAll("[data-section-close]").forEach(function (button) {
      button.addEventListener("click", function () {
        setSectionVisibility(button.dataset.sectionClose, false);
      });
    });

    scope.querySelectorAll("[data-optional-section]").forEach(function (section) {
      setSectionVisibility(section.dataset.optionalSection, !section.hidden);
    });
  }

  function initRoleSwitcher(scope, onRoleChange) {
    const form = scope.querySelector("[data-student-drawer-form]");
    const roleSelect = scope.querySelector("#id_role");

    if (!form || !roleSelect || form.dataset.roleSwitchEnabled !== "1" || typeof onRoleChange !== "function") {
      return;
    }

    roleSelect.addEventListener("change", function () {
      const nextRole = (roleSelect.value || "").trim();
      if (!nextRole) return;
      onRoleChange(nextRole);
    });
  }

  function initStudentDrawer(options) {
    const trigger = document.querySelector(options.triggerSelector);
    const overlay = document.querySelector(options.overlaySelector);
    const panel = document.querySelector(options.panelSelector);
    const body = document.querySelector(options.bodySelector);
    const closeButton = document.querySelector(options.closeButtonSelector);

    if (!trigger || !overlay || !panel || !body) return null;

    const state = {
      isLoaded: false,
      endpoint: trigger.dataset.drawerUrl || options.endpoint || ""
    };
    const duplicateModal = createDuplicateModal();

    function buildEndpoint(role) {
      const url = new URL(state.endpoint, window.location.origin);
      if (role) {
        url.searchParams.set("role", role);
      }
      return url.pathname + url.search + url.hash;
    }

    function setBodyState(html) {
      body.innerHTML = html;
    }

    function ensureDuplicateOverrideInput(form) {
      let input = form.querySelector("#id_duplicate_override, [name='duplicate_override']");
      if (!input) {
        input = document.createElement("input");
        input.type = "hidden";
        input.name = "duplicate_override";
        input.id = "id_duplicate_override";
        form.appendChild(input);
      }
      return input;
    }

    function formatDuplicateStudentMeta(student) {
      const parts = [];
      if (student.primary_phone) {
        parts.push(student.primary_phone);
      }
      if (student.birth_date) {
        parts.push(student.birth_date);
      }
      if (student.is_archived) {
        parts.push("arxivda");
      }
      return parts.join(" · ");
    }

    function closeDuplicateModal() {
      duplicateModal.pendingForm = null;
      duplicateModal.overlay.classList.remove("open");
      duplicateModal.overlay.setAttribute("aria-hidden", "true");
    }

    function openDuplicateModal(form, payload) {
      duplicateModal.pendingForm = form;
      duplicateModal.title.textContent = payload.title || "Duplicate tekshiruvi";
      duplicateModal.message.textContent = payload.message || "";
      duplicateModal.confirm.textContent = payload.confirm_label || "Yangi o'quvchi qilib qo'shish";
      duplicateModal.cancel.textContent = payload.cancel_label || "Bekor qilish";
      duplicateModal.list.innerHTML = "";

      const students = Array.isArray(payload.students) ? payload.students : [];
      if (students.length) {
        duplicateModal.listWrap.hidden = false;
        students.forEach(function (student) {
          const item = document.createElement("li");
          item.className = "student-drawer-duplicate__item";

          const name = document.createElement("strong");
          name.textContent = student.name || "Mavjud o'quvchi";

          const meta = document.createElement("span");
          meta.textContent = formatDuplicateStudentMeta(student);

          item.appendChild(name);
          if (meta.textContent) {
            item.appendChild(meta);
          }
          duplicateModal.list.appendChild(item);
        });
      } else {
        duplicateModal.listWrap.hidden = true;
      }

      duplicateModal.overlay.classList.add("open");
      duplicateModal.overlay.setAttribute("aria-hidden", "false");
    }

    function createDuplicateModal() {
      const modalOverlay = document.createElement("div");
      modalOverlay.className = "student-drawer-duplicate";
      modalOverlay.setAttribute("aria-hidden", "true");
      modalOverlay.innerHTML = [
        '<div class="student-drawer-duplicate__dialog" role="dialog" aria-modal="true" aria-labelledby="studentDrawerDuplicateTitle">',
        '  <div class="student-drawer-duplicate__eyebrow">Duplicate tekshiruvi</div>',
        '  <h3 id="studentDrawerDuplicateTitle" class="student-drawer-duplicate__title"></h3>',
        '  <p class="student-drawer-duplicate__message"></p>',
        '  <div class="student-drawer-duplicate__list-wrap" hidden>',
        '    <div class="student-drawer-duplicate__list-label">Mavjud o\'quvchilar</div>',
        '    <ul class="student-drawer-duplicate__list"></ul>',
        '  </div>',
        '  <div class="student-drawer-duplicate__actions">',
        '    <button type="button" class="student-drawer-duplicate__button student-drawer-duplicate__button--ghost" data-duplicate-cancel>Bekor qilish</button>',
        '    <button type="button" class="student-drawer-duplicate__button student-drawer-duplicate__button--primary" data-duplicate-confirm>Yangi o\'quvchi qilib qo\'shish</button>',
        '  </div>',
        '</div>'
      ].join("");
      document.body.appendChild(modalOverlay);

      const modal = {
        overlay: modalOverlay,
        title: modalOverlay.querySelector(".student-drawer-duplicate__title"),
        message: modalOverlay.querySelector(".student-drawer-duplicate__message"),
        listWrap: modalOverlay.querySelector(".student-drawer-duplicate__list-wrap"),
        list: modalOverlay.querySelector(".student-drawer-duplicate__list"),
        cancel: modalOverlay.querySelector("[data-duplicate-cancel]"),
        confirm: modalOverlay.querySelector("[data-duplicate-confirm]"),
        pendingForm: null
      };

      modalOverlay.addEventListener("click", function (event) {
        if (event.target === modalOverlay || event.target.closest("[data-duplicate-cancel]")) {
          closeDuplicateModal();
        }
      });

      modal.confirm.addEventListener("click", function () {
        if (!modal.pendingForm) {
          closeDuplicateModal();
          return;
        }
        ensureDuplicateOverrideInput(modal.pendingForm).value = "1";
        closeDuplicateModal();
        if (typeof modal.pendingForm.requestSubmit === "function") {
          modal.pendingForm.requestSubmit();
          return;
        }
        modal.pendingForm.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      });

      return modal;
    }

    function lockScroll(lock) {
      document.body.classList.toggle("student-drawer-open", lock);
    }

    function closeDrawer() {
      closeDuplicateModal();
      overlay.classList.remove("open");
      panel.classList.remove("open");
      panel.setAttribute("aria-hidden", "true");
      lockScroll(false);
    }

    function onSubmit(event) {
      event.preventDefault();
      const form = event.currentTarget;
      if (form.dataset.submitting === "1") return;
      form.dataset.submitting = "1";

      const submitButton = form.querySelector(".bq-sdrawer-submit");
      if (submitButton) {
        submitButton.disabled = true;
        submitButton.classList.add("is-loading");
      }

      fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: {
          "X-Requested-With": "XMLHttpRequest"
        }
      })
        .then(function (response) {
          var status = response.status;
          return response.json().then(function (data) {
            return { ok: response.ok, status: status, data: data };
          }).catch(function () {
            return { ok: false, status: status, data: null };
          });
        })
        .then(function (result) {
          if (result.data && result.data.ok) {
            closeDrawer();
            if (typeof options.onSuccess === "function") {
              options.onSuccess(result.data);
            }
            return;
          }

          if (result.data && result.data.duplicate_check) {
            openDuplicateModal(form, result.data.duplicate_check);
            return;
          }

          if (result.data && result.data.html) {
            state.endpoint = form.action;
            setBodyState(result.data.html);
            initDynamicContent();
            return;
          }

          var errMsg = (result.data && result.data.error)
            ? result.data.error
            : (result.status >= 500
                ? "Server xatosi (" + result.status + "). Iltimos qayta urinib koʻring."
                : "Saqlashda xatolik yuz berdi. Qayta urinib koʻring.");
          setBodyState('<div class="student-drawer__error">' + errMsg + '</div>');
        })
        .catch(function () {
          setBodyState(
            '<div class="student-drawer__error">Server bilan aloqa uzildi. Internet yoki sessiyani tekshirib qayta urinib ko\'ring.</div>'
          );
        })
        .finally(function () {
          form.dataset.submitting = "0";
          if (submitButton) {
            submitButton.disabled = false;
            submitButton.classList.remove("is-loading");
          }
        });
    }

    function initDynamicContent() {
      body.querySelectorAll("[data-student-drawer-close]").forEach(function (button) {
        button.addEventListener("click", closeDrawer);
      });

      initInputFormatting(body);
      initPasswordToggle(body);
      initCredentialGenerator(body);
      initGroupAssignments(body);
      initExtraFields(body);
      initOptionalSections(body);
      initRoleSwitcher(body, function (nextRole) {
        state.isLoaded = false;
        state.endpoint = buildEndpoint(nextRole);
        loadForm(true);
      });

      const form = body.querySelector("[data-student-drawer-form]");
      if (form) {
        form.addEventListener("submit", onSubmit);
      }
    }

    function loadForm(forceReload) {
      if (!state.endpoint) return;
      if (state.isLoaded && !forceReload) return;

      setBodyState('<div class="student-drawer__loading">Forma yuklanmoqda...</div>');

      fetch(state.endpoint, {
        headers: {
          "X-Requested-With": "XMLHttpRequest"
        }
      })
        .then(function (response) {
          if (!response.ok) {
            throw new Error("drawer-fetch-failed");
          }
          return response.text();
        })
        .then(function (html) {
          state.isLoaded = true;
          setBodyState(html);
          initDynamicContent();
        })
        .catch(function () {
          setBodyState(
            '<div class="student-drawer__error">Forma yuklanmadi. Sahifani yangilab qayta urinib ko\'ring.</div>'
          );
        });
    }

    function openDrawer(forceReload) {
      overlay.classList.add("open");
      panel.classList.add("open");
      panel.setAttribute("aria-hidden", "false");
      lockScroll(true);
      loadForm(forceReload);
    }

    trigger.addEventListener("click", function (event) {
      event.preventDefault();
      openDrawer(false);
    });

    overlay.addEventListener("click", closeDrawer);
    if (closeButton) {
      closeButton.addEventListener("click", closeDrawer);
    }

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && duplicateModal.overlay.classList.contains("open")) {
        closeDuplicateModal();
        return;
      }
      if (event.key === "Escape" && panel.classList.contains("open")) {
        closeDrawer();
      }
    });

    return {
      open: openDrawer,
      close: closeDrawer,
      reload: function () {
        state.isLoaded = false;
        openDrawer(true);
      }
    };
  }

  window.initStudentDrawer = initStudentDrawer;
})();
