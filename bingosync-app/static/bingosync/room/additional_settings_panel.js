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
                error: function(xhr) {
                    alert("Couldn't change your OBS source: " + xhr.responseText);
                    $box.prop("checked", !$box.prop("checked"));
                }
            });
        });
        $panel.find("#obs-regenerate").on("click", function() {
            if (!window.confirm("Make a new OBS link? The current one will stop working, " +
                                "and you'll need to paste the new one into OBS.")) {
                return;
            }
            $.ajax({
                url: "/api/obs/regenerate",
                type: "POST",
                contentType: "application/json",
                data: "{}",
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
