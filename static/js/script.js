// ============================================================
// MINI DARAZ - Frontend JavaScript
// ============================================================

document.addEventListener('DOMContentLoaded', function () {

    // ---- Quantity stepper on product detail page ----
    const qtyInput = document.getElementById('qty');
    if (qtyInput) {
        const minus = document.getElementById('qty-minus');
        const plus = document.getElementById('qty-plus');
        const max = parseInt(qtyInput.getAttribute('data-max') || '99', 10);
        minus.addEventListener('click', () => {
            let v = parseInt(qtyInput.value) - 1;
            if (v < 1) v = 1;
            qtyInput.value = v;
        });
        plus.addEventListener('click', () => {
            let v = parseInt(qtyInput.value) + 1;
            if (v > max) v = max;
            if (v < 1) v = 1;
            qtyInput.value = v;
        });
    }

    // ---- AJAX add to cart (from product cards) ----
    document.querySelectorAll('form.add-to-cart-form').forEach(form => {
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            const fd = new FormData(form);
            fetch(form.action, {
                method: 'POST',
                body: fd
            }).then(r => r.text()).then(() => {
                showToast('Product added to cart!', 'success');
                updateCartBadge();
            }).catch(() => showToast('Something went wrong', 'danger'));
        });
    });

    // ---- AJAX add to wishlist ----
    document.querySelectorAll('form.add-to-wishlist-form').forEach(form => {
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            const fd = new FormData(form);
            fetch(form.action, {
                method: 'POST',
                body: fd
            }).then(() => {
                showToast('Added to wishlist!', 'success');
                updateWishlistBadge();
            }).catch(() => showToast('Something went wrong', 'danger'));
        });
    });

    // ---- Star rating selector ----
    const stars = document.querySelectorAll('.rating-input i');
    const ratingInput = document.getElementById('rating-value');
    if (stars.length && ratingInput) {
        stars.forEach((star, idx) => {
            star.addEventListener('mouseenter', () => highlightStars(idx + 1));
            star.addEventListener('click', () => {
                ratingInput.value = idx + 1;
                highlightStars(idx + 1);
            });
        });
        document.querySelector('.rating-input').addEventListener('mouseleave', () => {
            highlightStars(parseInt(ratingInput.value) || 0);
        });
    }

    // ---- Mobile admin sidebar toggle ----
    const adminToggle = document.getElementById('adminSidebarToggle');
    if (adminToggle) {
        adminToggle.addEventListener('click', () => {
            document.getElementById('adminSidebar').classList.toggle('show');
        });
    }

    // ---- Flash sale countdown timer ----
    const timerEl = document.getElementById('flash-timer');
    if (timerEl) {
        let total = parseInt(timerEl.getAttribute('data-seconds') || '3600', 10);
        setInterval(() => {
            if (total <= 0) return;
            total--;
            const h = String(Math.floor(total / 3600)).padStart(2, '0');
            const m = String(Math.floor((total % 3600) / 60)).padStart(2, '0');
            const s = String(total % 60).padStart(2, '0');
            timerEl.textContent = `${h}:${m}:${s}`;
        }, 1000);
    }

    // ---- Auto-dismiss alerts ----
    setTimeout(() => {
        document.querySelectorAll('.alert').forEach(a => {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(a);
            if (bsAlert) bsAlert.close();
        });
    }, 5000);
});

// ---- Helpers ----
function highlightStars(count) {
    document.querySelectorAll('.rating-input i').forEach((s, i) => {
        s.classList.toggle('active', i < count);
        s.style.color = i < count ? 'var(--warning)' : '#ddd';
    });
}

function showToast(message, type) {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.style.cssText = 'position:fixed;top:80px;right:20px;z-index:9999;';
        document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = `alert alert-${type} alert-dismissible fade show`;
    toast.style.minWidth = '250px';
    toast.innerHTML = `${message}<button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;
    container.appendChild(toast);
    setTimeout(() => {
        if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, 3000);
}

function updateCartBadge() {
    fetch('/cart/count').then(r => r.json()).then(d => {
        const badge = document.querySelector('.fa-shopping-cart').nextElementSibling;
        if (badge) {
            badge.textContent = d.count;
            badge.style.display = d.count > 0 ? 'inline' : 'none';
        }
    }).catch(() => { });
}

function updateWishlistBadge() {
    fetch('/wishlist/count').then(r => r.json()).then(d => {
        const badge = document.querySelector('.fa-heart').nextElementSibling;
        if (badge) {
            badge.textContent = d.count;
            badge.style.display = d.count > 0 ? 'inline' : 'none';
        }
    }).catch(() => { });
}

// ---- Admin: live preview of selected product image ----
const imageInput = document.getElementById('image');
if (imageInput) {
    const preview = document.getElementById('image-preview');
    imageInput.addEventListener('change', function () {
        const file = this.files && this.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = e => { preview.src = e.target.result; };
            reader.readAsDataURL(file);
        }
    });
}