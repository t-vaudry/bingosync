// Display-only options for this viewer. They never touch the room, and are
// remembered in this browser.
//
// Full Width Board and Solo Blackout View are ported from the Celeste
// Bingosync fork (Blackout view originally by Rhuan).
var AdditionalSettingsPanel = (function(){
    "use strict";

    var STORAGE_PREFIX = "bingosync.";
    // Full width board: space left under the board, and the shortest cell (px)
    // it is shrunk to in a very short window. The gap is only a sliver for
    // the commentator's Counts panel, which sits below the board.
    var BOARD_BOTTOM_GAP = 8;
    var MIN_CELL_HEIGHT = 40;

    function load(key) {
        try {
            return window.localStorage.getItem(STORAGE_PREFIX + key) === "1";
        } catch (e) {
            return false;
        }
    }

    function save(key, value) {
        try {
            window.localStorage.setItem(STORAGE_PREFIX + key, value ? "1" : "0");
        } catch (e) {
            // Storage unavailable (private mode); the setting just won't persist.
        }
    }

    var AdditionalSettingsPanel = function($panel, $layout, board, colorChooser) {
        this.$panel = $panel;
        this.$layout = $layout;
        this.board = board;
        this.colorChooser = colorChooser;
        this.$fullwidth = $panel.find("#fullwidth-toggle");
        this.$blackout = $panel.find("#blackoutview-toggle");

        var that = this;
        this.$fullwidth.on("change", function() { that.setFullWidth(this.checked); });
        this.$blackout.on("change", function() { that.setBlackoutView(this.checked); });
        $panel.find(".collapse-button").on("mousedown", function() {
            $panel.find(".panel-body").toggle(50);
        });

        // The blackout view shows the color currently chosen to mark with.
        // Delegated: a counter's target buttons are created after this runs.
        $(document).on("click", ".color-chooser", function() {
            if (that.$blackout.prop("checked")) {
                setTimeout(function() { that.applyBlackoutView(); }, 0);
            }
        });

        // Unlike the toggles above, the OBS options live on the server: the
        // OBS link is the same wherever this account is used.
        $panel.find("#obs-room-toggle").on("change", function() {
            var $box = $(this);
            $.ajax({
                url: "/api/obs/room",
                type: "POST",
                contentType: "application/json",
                data: JSON.stringify({room: $box.data("room"), selected: this.checked}),
                success: function(result) {
                    // The server decides which room really is the source
                    // (e.g. unticking the only live room keeps it ticked)
                    $box.prop("checked", result.selected);
                },
                error: function(xhr) {
                    alert("Couldn't change your OBS source: " + xhr.responseText);
                    $box.prop("checked", !$box.prop("checked"));
                }
            });
        });

        // Ticking this in another room (or that room closing) changes which
        // room is the source, so keep the box in step with the OBS link.
        var $obsBox = $panel.find("#obs-room-toggle");
        if ($obsBox.length) {
            setInterval(function() {
                var obsUrl = $("#copy-obs-link").data("url");  // changes on regenerate
                if (!obsUrl) { return; }
                $.getJSON(obsUrl + "/state", function(state) {
                    $obsBox.prop("checked", state.room === $obsBox.data("room"));
                });
            }, 10000);
        }
        $panel.find("#obs-regenerate").on("click", function() {
            if (!window.confirm("Make a new OBS link? The current one will stop working, " +
                                "and you'll need to paste the new one into OBS.")) {
                return;
            }
            $.ajax({
                url: "/api/obs/regenerate",
                type: "POST",
                contentType: "application/json",
                data: JSON.stringify({room: window.sessionStorage.getItem("room")}),
                success: function(result) {
                    $("#copy-obs-link").data("url", result.url);
                    window.alert("New OBS link made. Use \"Copy OBS link\" to copy it.");
                },
                error: function(xhr) {
                    alert("Couldn't make a new OBS link: " + xhr.responseText);
                }
            });
        });

        this.$fullwidth.prop("checked", load("fullwidth"));
        this.$blackout.prop("checked", load("blackout"));
        this.setFullWidth(this.$fullwidth.prop("checked"), /*persist=*/false);
        this.applyBlackoutView();

        // Refit when the window changes, when late loads (fonts, the page
        // itself) move the header and so the board, and when what sits above
        // the board or the cells change. The fit is cheap and idempotent, so
        // it runs synchronously. It only changes styles, never the children
        // the observer watches, so it can't loop.
        var fit = function() { that.fitBoard(); };
        $(window).on("resize", fit);
        $(window).on("load", fit);
        if (document.fonts && document.fonts.ready) {
            document.fonts.ready.then(fit);
        }
        if (window.MutationObserver) {
            var observer = new MutationObserver(fit);
            // The board's own children (cards, strips) come in through
            // .board-container's subtree. The board column is watched only for
            // children added or removed directly (counter controls), so the
            // commentator's Counts panel polling doesn't refit the board.
            var watched = [
                [$(".board-container")[0], true],
                [$(".room-board-col")[0], false],
                [$(".room-header")[0], true]
            ];
            watched.forEach(function(pair) {
                if (pair[0]) { observer.observe(pair[0], {childList: true, subtree: pair[1]}); }
            });
        }
    };

    AdditionalSettingsPanel.prototype.setFullWidth = function(on, persist) {
        this.$layout.toggleClass("room-layout-fullwidth", on);
        this.$layout.closest(".room-page").toggleClass("room-page-fullwidth", on);
        if (persist !== false) { save("fullwidth", on); }
        if (on) {
            this.fitBoard();
        } else {
            // Back to the standard cell size: the layout's own size applies
            this.$layout[0].style.removeProperty("--board-cell-h");
            this.board.refreshSquareLayout();
        }
    };

    // Full width board: the cells are as tall as fit the visible window below
    // the top of the board, so the board never needs scrolling. Their width
    // is whatever the full-width table gives them.
    AdditionalSettingsPanel.prototype.fitBoard = function() {
        if (!this.$layout.hasClass("room-layout-fullwidth")) { return; }
        var cell = $("#bingo .square")[0];
        var table = $("#bingo")[0];
        var boardContainer = $(".board-container")[0];
        if (!cell || !table || !boardContainer || cell.offsetHeight === 0) { return; }

        var perColumn = this.board.size || 5;
        // The label row and column and the cell spacing: measured, not hardcoded
        var chromeHeight = table.offsetHeight - perColumn * cell.offsetHeight;
        // Document position, not the viewport's: the fit doesn't change as the
        // page scrolls, and the header and controls above stay on screen
        var boardTop = $(boardContainer).offset().top;
        var availableHeight = window.innerHeight - boardTop - BOARD_BOTTOM_GAP - chromeHeight;

        var cellHeight = Math.max(MIN_CELL_HEIGHT, Math.floor(availableHeight / perColumn));
        this.$layout[0].style.setProperty("--board-cell-h", cellHeight + "px");
        this.board.refreshSquareLayout();
    };

    AdditionalSettingsPanel.prototype.setBlackoutView = function(on) {
        save("blackout", on);
        this.applyBlackoutView();
    };

    // A player marks with the color chooser's color; a counter views the
    // target they picked (those buttons carry the color as a class).
    AdditionalSettingsPanel.prototype.chosenColor = function() {
        var cls = $(".color-chooser.chosen-color").first().attr("class") || "";
        var match = cls.match(/([a-z]+)square/);
        return match ? match[1] : this.colorChooser.getChosenColor();
    };

    AdditionalSettingsPanel.prototype.applyBlackoutView = function() {
        var on = this.$blackout.prop("checked");
        this.board.setBlackoutView(on ? this.chosenColor() : null);
    };

    return AdditionalSettingsPanel;
})();
