// Adds a "Show"/"Hide" toggle to every password field on the page, including
// fields inserted later (e.g. inside dialogs).
(function () {
    function enhance(input) {
        if (input.dataset.pwToggle) return;
        input.dataset.pwToggle = "1";

        var wrap = document.createElement("div");
        wrap.className = "password-toggle-wrap";
        input.parentNode.insertBefore(wrap, input);
        wrap.appendChild(input);

        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "password-toggle-btn";
        btn.textContent = "Show";
        btn.setAttribute("aria-pressed", "false");
        btn.setAttribute("aria-label", "Show password");
        if (input.id) btn.setAttribute("aria-controls", input.id);
        btn.addEventListener("click", function () {
            var show = input.type === "password";
            input.type = show ? "text" : "password";
            btn.textContent = show ? "Hide" : "Show";
            btn.setAttribute("aria-pressed", show ? "true" : "false");
            btn.setAttribute("aria-label", show ? "Hide password" : "Show password");
        });
        wrap.appendChild(btn);
    }

    function scan(root) {
        var inputs = root.querySelectorAll('input[type="password"]');
        for (var i = 0; i < inputs.length; i++) enhance(inputs[i]);
    }

    function init() {
        scan(document);
        new MutationObserver(function () { scan(document); })
            .observe(document.body, { childList: true, subtree: true });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
