// Display-only options for this viewer. They never touch the room, and are
// remembered in this browser.
//
// Full Width Board and Solo Blackout View are ported from the Celeste
// Bingosync fork (Blackout view originally by Rhuan).
var AdditionalSettingsPanel = (function(){
    "use strict";

    var STORAGE_PREFIX = "bingosync.";

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
        $(".color-chooser").on("click", function() {
            if (that.$blackout.prop("checked")) {
                that.applyBlackoutView();
            }
        });

        this.$fullwidth.prop("checked", load("fullwidth"));
        this.$blackout.prop("checked", load("blackout"));
        this.setFullWidth(this.$fullwidth.prop("checked"), /*persist=*/false);
        this.applyBlackoutView();
    };

    AdditionalSettingsPanel.prototype.setFullWidth = function(on, persist) {
        this.$layout.toggleClass("room-layout-fullwidth", on);
        if (persist !== false) { save("fullwidth", on); }
        // Squares change size: recompute color skews and refit goal text.
        $(window).trigger("resize");
    };

    AdditionalSettingsPanel.prototype.setBlackoutView = function(on) {
        save("blackout", on);
        this.applyBlackoutView();
    };

    AdditionalSettingsPanel.prototype.applyBlackoutView = function() {
        var on = this.$blackout.prop("checked");
        this.board.setBlackoutView(on ? this.colorChooser.getChosenColor() : null);
    };

    return AdditionalSettingsPanel;
})();
