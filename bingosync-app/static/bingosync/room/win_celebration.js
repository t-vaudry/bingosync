/**
 * Winner celebration: a dismissible pop-up with a burst of confetti.
 * Triggered by a "game_won" websocket event. Self-contained, no dependencies.
 */
var showWinCelebration = (function() {
    "use strict";

    var CONFETTI_COLORS = [
        "#ffd54a", "#ff6b6b", "#4fb585", "#6ea3d8",
        "#c9a95a", "#b57edc", "#ff9f43", "#ffffff"
    ];

    function launchConfetti() {
        var canvas = document.createElement("canvas");
        canvas.className = "win-confetti-canvas";
        document.body.appendChild(canvas);
        var ctx = canvas.getContext("2d");

        function resize() {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        }
        resize();
        window.addEventListener("resize", resize);

        var particles = [];
        for (var i = 0; i < 200; i++) {
            particles.push({
                x: Math.random() * canvas.width,
                // Spread from above the viewport to mid-screen so there is an
                // immediate on-screen burst that keeps streaming down.
                y: Math.random() * (canvas.height * 1.5) - canvas.height,
                w: 6 + Math.random() * 6,
                h: 8 + Math.random() * 8,
                color: CONFETTI_COLORS[Math.floor(Math.random() * CONFETTI_COLORS.length)],
                vx: -2 + Math.random() * 4,
                vy: 2 + Math.random() * 4,
                rot: Math.random() * Math.PI,
                vr: -0.2 + Math.random() * 0.4
            });
        }

        var start = Date.now();
        var duration = 4500;
        function frame() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            var elapsed = Date.now() - start;
            for (var i = 0; i < particles.length; i++) {
                var p = particles[i];
                p.x += p.vx;
                p.y += p.vy;
                p.vy += 0.05; // gravity
                p.rot += p.vr;
                ctx.save();
                ctx.translate(p.x, p.y);
                ctx.rotate(p.rot);
                ctx.globalAlpha = Math.max(0, 1 - elapsed / duration);
                ctx.fillStyle = p.color;
                ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
                ctx.restore();
            }
            if (elapsed < duration) {
                requestAnimationFrame(frame);
            } else {
                window.removeEventListener("resize", resize);
                canvas.remove();
            }
        }
        requestAnimationFrame(frame);
    }

    function showWinCelebration(winnerName, goals) {
        // Don't stack duplicates if two events arrive close together.
        if (document.querySelector(".win-overlay")) {
            return;
        }

        var overlay = document.createElement("div");
        overlay.className = "win-overlay";

        var card = document.createElement("div");
        card.className = "win-card";

        var trophy = document.createElement("div");
        trophy.className = "win-trophy";
        trophy.textContent = "🏆";

        var heading = document.createElement("div");
        heading.className = "win-heading";
        heading.textContent = "We have a winner!";

        var name = document.createElement("div");
        name.className = "win-name";
        name.textContent = winnerName; // textContent keeps player names XSS-safe

        var sub = document.createElement("div");
        sub.className = "win-sub";
        var goalCount = goals || 13;
        sub.textContent = "first to " + goalCount + " goals";

        var btn = document.createElement("button");
        btn.className = "btn btn-primary win-dismiss";
        btn.textContent = "Dismiss";

        function close() {
            overlay.remove();
            document.removeEventListener("keydown", onKey);
        }
        function onKey(e) {
            if (e.key === "Escape") {
                close();
            }
        }

        btn.addEventListener("click", close);
        overlay.addEventListener("click", function(e) {
            if (e.target === overlay) {
                close();
            }
        });
        document.addEventListener("keydown", onKey);

        card.appendChild(trophy);
        card.appendChild(heading);
        card.appendChild(name);
        card.appendChild(sub);
        card.appendChild(btn);
        overlay.appendChild(card);
        document.body.appendChild(overlay);

        launchConfetti();
    }

    return showWinCelebration;
})();
window.showWinCelebration = showWinCelebration;
