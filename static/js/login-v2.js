document.addEventListener('DOMContentLoaded', function() {
    // Password Toggle
    const togglePassword = document.getElementById('togglePassword');
    const passwordInput = document.getElementById('passwordInput');
    const eyeIcon = document.getElementById('eyeIcon');
    const eyeOffIcon = document.getElementById('eyeOffIcon');

    if (togglePassword && passwordInput) {
        togglePassword.addEventListener('click', function() {
            const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
            passwordInput.setAttribute('type', type);
            
            // Toggle icons
            if (type === 'text') {
                eyeIcon.classList.add('hidden');
                eyeOffIcon.classList.remove('hidden');
            } else {
                eyeIcon.classList.remove('hidden');
                eyeOffIcon.classList.add('hidden');
            }
        });
    }

    // Remember Me Toggle
    const rememberMeContainer = document.getElementById('rememberMeContainer');
    const rememberMeCheckbox = document.getElementById('rememberMeCheckbox');
    const rememberMeCheckIcon = document.getElementById('rememberMeCheckIcon');

    if (rememberMeContainer && rememberMeCheckbox) {
        rememberMeContainer.addEventListener('click', function() {
            rememberMeCheckbox.checked = !rememberMeCheckbox.checked;
            
            if (rememberMeCheckbox.checked) {
                rememberMeContainer.classList.remove('bg-slate-900/50', 'border-white/10');
                rememberMeContainer.classList.add('bg-teal-500', 'border-teal-500');
                rememberMeCheckIcon.classList.remove('hidden');
            } else {
                rememberMeContainer.classList.add('bg-slate-900/50', 'border-white/10');
                rememberMeContainer.classList.remove('bg-teal-500', 'border-teal-500');
                rememberMeCheckIcon.classList.add('hidden');
            }
        });
    }
});
