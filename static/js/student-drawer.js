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
    return "+998" + (parts.length ? " " + parts.join(" ") : " ");
  }

  function formatPassportValue(value) {
    const clean = String(value || "").toUpperCase().replace(/[^A-Z0-9]/g, "");
    const letters = clean.replace(/[^A-Z]/g, "").slice(0, 2);
    const numbers = clean.replace(/[^0-9]/g, "").slice(0, 7);
    return letters + numbers;
  }

  function initInputFormatting(scope) {
    scope.querySelectorAll("#id_telefon1, #id_telefon2").forEach(function (input) {
      function applyPhoneMask() {
        input.value = formatPhoneValue(input.value);
      }

      applyPhoneMask();
      input.addEventListener("focus", applyPhoneMask);
      input.addEventListener("input", applyPhoneMask);
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

  function initGroupPrice(scope) {
    const form = scope.querySelector("[data-student-drawer-form]");
    const groupSelect = scope.querySelector("#id_group");
    const priceInput = scope.querySelector("#id_kurs_narhi");
    const priceBlock = scope.querySelector("[data-drawer-price-block]");
    const template = form ? form.dataset.groupPriceTemplate : "";

    if (!form || !groupSelect || !priceInput || !priceBlock || !template) return;

    function hidePrice() {
      priceBlock.style.display = "none";
      priceInput.value = "";
    }

    function showPrice(value) {
      priceBlock.style.display = "";
      if (value !== undefined && value !== null && value !== "") {
        priceInput.value = value;
      }
    }

    function loadPrice() {
      const groupId = groupSelect.value;
      if (!groupId) {
        hidePrice();
        return;
      }

      fetch(replaceGroupId(template, groupId), {
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
          showPrice(data.price || "");
        })
        .catch(function () {
          showPrice(priceInput.value || "");
        });
    }

    groupSelect.addEventListener("change", loadPrice);
    if (groupSelect.value) {
      loadPrice();
    } else {
      hidePrice();
    }
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
    function clearSection(sectionName) {
      const section = scope.querySelector('[data-optional-section="' + sectionName + '"]');
      if (!section) return;

      section.querySelectorAll("input, textarea, select").forEach(function (input) {
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

    function setSectionVisibility(sectionName, visible) {
      const section = scope.querySelector('[data-optional-section="' + sectionName + '"]');
      const toggle = scope.querySelector('[data-section-toggle="' + sectionName + '"]');
      if (!section || !toggle) return;

      section.hidden = !visible;
      toggle.classList.toggle("is-active", visible);

      if (visible) {
        const input = section.querySelector("input, textarea, select");
        if (input) input.focus();
        return;
      }

      clearSection(sectionName);
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

    function lockScroll(lock) {
      document.body.classList.toggle("student-drawer-open", lock);
    }

    function closeDrawer() {
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
          return response.json().then(function (data) {
            return { ok: response.ok, data: data };
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

          if (result.data && result.data.html) {
            state.endpoint = form.action;
            setBodyState(result.data.html);
            initDynamicContent();
            return;
          }

          setBodyState(
            '<div class="student-drawer__error">Formani saqlashda xatolik yuz berdi. Qayta urinib ko\'ring.</div>'
          );
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
      initGroupPrice(body);
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
