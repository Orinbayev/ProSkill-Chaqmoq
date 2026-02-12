async function markAllRead() {
    const btn = document.getElementById('markAllReadBtn');
    if (!btn) return;

    btn.innerHTML = '<i class="bi bi-hourglass-split me-1 animate-spin"></i> ...';

    try {
        const response = await fetch('/notifications/api/read-all/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json'
            }
        });
        const data = await response.json();

        if (data.success) {
            // Remove badges
            document.querySelectorAll('.notification-badge').forEach(el => el.remove());
            document.querySelectorAll('.notification-count-badge').forEach(el => el.remove());

            // Remove unread bg
            document.querySelectorAll('.notification-list .bg-light').forEach(el => {
                el.classList.remove('bg-light', 'bg-opacity-10');
            });

            btn.innerHTML = '<i class="bi bi-check2-all me-1"></i> Bajarildi';
            btn.disabled = true;
            setTimeout(() => {
                btn.innerHTML = '<i class="bi bi-check2-all me-1"></i> O\'qildi';
            }, 2000);
        }
    } catch (error) {
        console.error(error);
        btn.innerHTML = '<i class="bi bi-x-circle me-1"></i> Xatolik';
    }
}

function getCsrfToken() {
    const name = 'csrftoken';
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
