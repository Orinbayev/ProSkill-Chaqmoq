document.addEventListener("DOMContentLoaded", () => {
    const fileInput = document.getElementById("id_file");
    const fileNameNode = document.querySelector("[data-file-name]");

    if (fileInput && fileNameNode) {
        const updateFileName = () => {
            const [file] = fileInput.files || [];
            fileNameNode.textContent = file ? `Tanlangan fayl: ${file.name}` : "Fayl tanlanmagan";
        };

        fileInput.addEventListener("change", updateFileName);
        updateFileName();
    }

    const dropdowns = Array.from(document.querySelectorAll("details.mkt-dropdown"));
    if (!dropdowns.length) {
        return;
    }

    document.addEventListener("click", (event) => {
        const target = event.target;
        dropdowns.forEach((dropdown) => {
            if (!dropdown.contains(target)) {
                dropdown.removeAttribute("open");
            }
        });
    });

    document.addEventListener("keydown", (event) => {
        if (event.key !== "Escape") {
            return;
        }
        dropdowns.forEach((dropdown) => dropdown.removeAttribute("open"));
    });
});
