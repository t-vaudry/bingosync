var PlayersPanel = (function(){
    "use strict";

    var PlayersPanel = function($playersPanel, currentPlayer){
        this.$playersPanel = $playersPanel;
        this.currentPlayer = currentPlayer;
        // Called whenever players join, leave, or change color or role
        // (the counter's "Counting for" buttons listen to this).
        this.onChange = null;

        // Initialize buttons for existing players in the DOM
        this._initializeExistingPlayers();
    };

    // Everyone with the Player role who's in the panel, with their color.
    PlayersPanel.prototype.getPlayers = function() {
        var players = [];
        this.$playersPanel.find('.player-panel-entry').each(function() {
            var $entry = $(this);
            if ($entry.hasClass('spectator-entry') || ($entry.attr('data-role') || 'player') !== 'player') {
                return;
            }
            var colorClass = ($entry.find('.goalcounter').attr('class') || '').split(' ')[1] || '';
            players.push({
                uuid: $entry.attr('id'),
                name: $entry.find('.playername').text().trim(),
                color: colorClass.replace(/square$/, '')
            });
        });
        return players;
    };

    // Colors claim squares; players are associated with a color. The colors
    // in use, each labelled with its player's name when exactly one player
    // uses it, otherwise with the color's name.
    PlayersPanel.prototype.getColorGroups = function() {
        var groups = {};
        var order = [];
        this.getPlayers().forEach(function(player) {
            if (!player.color) {
                return;
            }
            if (!groups[player.color]) {
                groups[player.color] = [];
                order.push(player.color);
            }
            groups[player.color].push(player.name);
        });
        return order.map(function(color) {
            var names = groups[color];
            return {color: color, label: names.length === 1 ? names[0] : color, players: names};
        });
    };

    PlayersPanel.prototype.colorLabel = function(color) {
        var group = this.getColorGroups().filter(function(g) { return g.color === color; })[0];
        return group ? group.label : color;
    };

    PlayersPanel.prototype._notifyChange = function() {
        if (this.onChange) {
            this.onChange();
        }
    };

    // The management buttons a Gamemaster gets on each entry
    var MANAGEMENT_BUTTONS = '.role-change-btn, .kick-player-btn, .assign-counter-btn, .change-color-btn';

    // A player's details as read back from their entry in the panel
    PlayersPanel.prototype._playerJsonFromEntry = function($playerEntry) {
        var colorClass = ($playerEntry.find('.goalcounter').attr('class') || '').split(' ')[1] || '';
        return {
            uuid: $playerEntry.attr('id'),
            name: $playerEntry.find('.playername').text().trim(),
            role: $playerEntry.attr('data-role') || 'player',
            color: colorClass.replace(/square$/, '') || null,
            is_logged_in: $playerEntry.attr('data-is-logged-in') === 'true',
            monitoring_color: $playerEntry.attr('data-monitoring-color') || null
        };
    };

    PlayersPanel.prototype._initializeExistingPlayers = function() {
        var self = this;
        this.$playersPanel.find('.player-panel-entry').each(function() {
            var $playerEntry = $(this);
            // Skip if buttons already exist
            if ($playerEntry.find(MANAGEMENT_BUTTONS).length > 0) {
                return;
            }
            // Counters pick who they count for with the "Counting for"
            // buttons above the board (counter.js), not a button here.
            self._appendManagementButtons($playerEntry, self._playerJsonFromEntry($playerEntry));
        });
    };

    PlayersPanel.prototype._refreshAllManagementButtons = function() {
        var self = this;
        this.$playersPanel.find(MANAGEMENT_BUTTONS).remove();
        this.$playersPanel.find('.player-panel-entry').each(function() {
            var $playerEntry = $(this);
            self._appendManagementButtons($playerEntry, self._playerJsonFromEntry($playerEntry));
        });
    };

    PlayersPanel.prototype.setPlayer = function(playerJson) {
        var isSpectator = playerJson["role"] === "spectator";
        var isCounter = playerJson["role"] === "counter";

        if(this.$playersPanel.find("#" + playerJson["uuid"]).length === 0) {
            // Player doesn't exist, insert them
            this._addEntry(playerJson);
        } else {
            // Player exists, update them
            var $playerEntry = this.$playersPanel.find("#" + playerJson["uuid"]);
            
            // Update data attributes
            $playerEntry.attr('data-role', playerJson["role"]);
            $playerEntry.attr('data-is-logged-in', playerJson["is_logged_in"] ? 'true' : 'false');
            if (playerJson["monitoring_color"]) {
                $playerEntry.attr('data-monitoring-color', playerJson["monitoring_color"]);
            } else {
                $playerEntry.removeAttr('data-monitoring-color');
            }
            
            // Players, counters and spectators each have their own section, so
            // a change between them means moving the entry
            var wasSpectator = $playerEntry.hasClass("spectator-entry");
            var wasCounter = $playerEntry.hasClass("counter-entry");
            if (isSpectator !== wasSpectator || isCounter !== wasCounter) {
                $playerEntry.remove();
                this._removeEmptySections();
                this._addEntry(playerJson);
            } else {
                // Just update the existing entry
                if (!isSpectator && !isCounter) {
                    // Update color for non-spectators
                    var $playerGoalCounter = $playerEntry.find(".goalcounter");
                    COLORS.forEach(function(color) {
                        $playerGoalCounter.removeClass(getSquareColorClass(color));
                    });
                    $playerGoalCounter.addClass(getSquareColorClass(playerJson["color"]));
                }
                
                // Update role badge
                if (!isSpectator && !isCounter) {
                    $playerEntry.find(".player-role-badge").replaceWith(this._createRoleBadge(playerJson));
                }
            }
        }
        this._notifyChange();
    };

    PlayersPanel.prototype._addEntry = function(playerJson) {
        if (playerJson["role"] === "spectator") {
            this._addSpectator(playerJson);
        } else if (playerJson["role"] === "counter") {
            this._addCounter(playerJson);
        } else {
            this._addPlayer(playerJson);
        }
    };

    // Counters and spectators are listed in their own sections below the
    // players. Returns the section for the given kind, creating it if needed.
    PlayersPanel.prototype._ensureSection = function(kind) {
        var $section = this.$playersPanel.find("." + kind + "s-section");
        if ($section.length === 0) {
            $section = $("<div>", {"class": kind + "s-section"});
            $section.append($("<div>", {"class": kind + "s-header", text: kind === "counter" ? "Counters" : "Spectators"}));
            var $spectators = this.$playersPanel.find(".spectators-section");
            if (kind === "counter" && $spectators.length > 0) {
                // Counters sit above spectators
                $spectators.before($section);
            } else {
                this.$playersPanel.append($section);
            }
        }
        return $section;
    };

    PlayersPanel.prototype._removeEmptySections = function() {
        this.$playersPanel.find(".counters-section, .spectators-section").each(function() {
            if ($(this).find(".player-panel-entry").length === 0) {
                $(this).remove();
            }
        });
    };

    PlayersPanel.prototype._appendManagementButtons = function($entry, playerJson) {
        if (!this.currentPlayer || this.currentPlayer.role !== 'gamemaster') {
            return;
        }
        $entry.append(this._createRoleButton(playerJson));
        // No kicking yourself
        if (playerJson["uuid"] !== this.currentPlayer.uuid) {
            $entry.append(this._createKickButton(playerJson));
        }
        if (playerJson["role"] === "player") {
            $entry.append(this._createColorButton(playerJson));
        }
        if (playerJson["role"] === "counter") {
            $entry.append(this._createAssignCounterButton(playerJson));
        }
    };

    PlayersPanel.prototype._addCounter = function(playerJson) {
        var counterDiv = $("<div>", {"id": playerJson["uuid"], "class": "player-panel-entry counter-entry"});
        counterDiv.attr('data-role', 'counter');
        counterDiv.attr('data-is-logged-in', playerJson["is_logged_in"] ? 'true' : 'false');
        if (playerJson["monitoring_color"]) {
            counterDiv.attr('data-monitoring-color', playerJson["monitoring_color"]);
        }

        counterDiv.append($("<span>", {"class": "playername", text: " " + playerJson["name"]}));
        if (playerJson["monitoring_color"]) {
            counterDiv.append(this._counterBadge(this.colorLabel(playerJson["monitoring_color"])));
        }
        this._appendManagementButtons(counterDiv, playerJson);

        this._ensureSection("counter").append(counterDiv);
    };

    PlayersPanel.prototype._addPlayer = function(playerJson) {
        var colorClass = getSquareColorClass(playerJson["color"]);
        var goalCounter = $("<span>", {"class": "goalcounter " + colorClass, html: "<span class=\"squarecounter\" title=\"Squares with color.\">0</span> <span class=\"rowcounter\" title=\"Rows with color.\">(0)</span>"});

        var playerName = $("<span>", {"class": "playername", text: " " + playerJson["name"]});
        
        // Add role badge
        var roleBadge = this._createRoleBadge(playerJson);
        
        var playerDiv = $("<div>", {"id": playerJson["uuid"], "class": "player-panel-entry"});
        
        // Set data attributes for role and monitoring
        playerDiv.attr('data-role', playerJson["role"]);
        playerDiv.attr('data-is-logged-in', playerJson["is_logged_in"] ? 'true' : 'false');
        if (playerJson["monitoring_color"]) {
            playerDiv.attr('data-monitoring-color', playerJson["monitoring_color"]);
        }
        
        playerDiv.append(goalCounter);
        playerDiv.append(playerName);
        playerDiv.append(roleBadge);
        
        this._appendManagementButtons(playerDiv, playerJson);

        // Players go above the counters and spectators sections
        var $firstSection = this.$playersPanel.find(".counters-section, .spectators-section").first();
        if ($firstSection.length > 0) {
            $firstSection.before(playerDiv);
        } else {
            this.$playersPanel.append(playerDiv);
        }
    };

    PlayersPanel.prototype._addSpectator = function(playerJson) {
        var playerName = $("<span>", {"class": "playername", text: " " + playerJson["name"]});
        var spectatorDiv = $("<div>", {"id": playerJson["uuid"], "class": "player-panel-entry spectator-entry"});
        
        // Set data attributes
        spectatorDiv.attr('data-role', 'spectator');
        spectatorDiv.attr('data-is-logged-in', playerJson["is_logged_in"] ? 'true' : 'false');
        
        spectatorDiv.append(playerName);
        
        this._appendManagementButtons(spectatorDiv, playerJson);
        
        this._ensureSection("spectator").append(spectatorDiv);
    };

    PlayersPanel.prototype._createRoleBadge = function(playerJson) {
        var roleText = "";
        var roleTitle = "Role: " + playerJson["role"];
        
        if (playerJson["role"] === "gamemaster") {
            roleText = "[GM]";
        }
        
        return $("<span>", {
            "class": "player-role-badge",
            "title": roleTitle,
            "text": roleText
        });
    };

    PlayersPanel.prototype._createRoleButton = function(playerJson) {
        var self = this;
        
        // Don't create role button for Gamemaster (role is permanent)
        if (playerJson["role"] === "gamemaster") {
            return $("<span>"); // Return empty span
        }
        
        var button = $("<button>", {
            "class": "btn btn-xs btn-default role-change-btn",
            "text": "Change Role",
            "title": "Change player role",
            "data-player-uuid": playerJson["uuid"],
            "data-player-name": playerJson["name"]
        });
        
        button.on("click", function(e) {
            e.preventDefault();
            self._showRoleChangeDialog(playerJson);
        });
        
        return button;
    };

    PlayersPanel.prototype._showRoleChangeDialog = function(playerJson) {
        var self = this;
        var currentRole = playerJson["role"];
        var isCurrentPlayer = playerJson["uuid"] === this.currentPlayer.uuid;
        var isCurrentPlayerGM = this.currentPlayer.role === 'gamemaster';
        
        // Create role selection dialog
        var roles = [];
        
        // RULE: Gamemaster role cannot be changed (no transfers, no self-demotion)
        if (currentRole === 'gamemaster') {
            alert("Gamemaster role cannot be changed. The Gamemaster role is permanent and cannot be transferred.");
            return;
        }
        
        // RULE: Cannot assign Gamemaster role to anyone (only at room creation)
        // Normal role changes: Player <-> Counter <-> Spectator
        roles.push({value: "player", label: "Player"});
        roles.push({value: "counter", label: "Counter"});
        roles.push({value: "spectator", label: "Spectator"});
        
        var dialogHtml = '<div class="role-change-dialog">';
        dialogHtml += '<p>Change role for <strong class="player-name-display"></strong></p>';
        dialogHtml += '<select class="form-control role-select">';
        roles.forEach(function(role) {
            var selected = role.value === currentRole ? ' selected' : '';
            dialogHtml += '<option value="' + role.value + '"' + selected + '>' + role.label + '</option>';
        });
        dialogHtml += '</select>';
        dialogHtml += '<div class="m-t-s">';
        dialogHtml += '<button class="btn btn-primary btn-sm confirm-role-change">Confirm</button> ';
        dialogHtml += '<button class="btn btn-default btn-sm cancel-role-change">Cancel</button>';
        dialogHtml += '</div>';
        dialogHtml += '</div>';
        
        // Show dialog (using a simple modal approach)
        var $dialog = $(dialogHtml);
        // Safely set player name using text() to prevent XSS
        $dialog.find('.player-name-display').text(playerJson["name"]);
        var $overlay = $('<div class="role-change-overlay"></div>');
        
        $('body').append($overlay);
        $('body').append($dialog);
        
        // Handle confirm
        $dialog.find('.confirm-role-change').on('click', function() {
            var newRole = $dialog.find('.role-select').val();
            self._assignRole(playerJson["uuid"], newRole);
            $dialog.remove();
            $overlay.remove();
        });
        
        // Handle cancel
        $dialog.find('.cancel-role-change').on('click', function() {
            $dialog.remove();
            $overlay.remove();
        });
        
        // Close on overlay click
        $overlay.on('click', function() {
            $dialog.remove();
            $overlay.remove();
        });
    };

    PlayersPanel.prototype._assignRole = function(targetPlayerUuid, newRole) {
        var roomUuid = window.sessionStorage.getItem("room");
        
        $.ajax({
            url: "/api/assign-role",
            type: "POST",
            contentType: "application/json",
            data: JSON.stringify({
                room: roomUuid,
                target_player_uuid: targetPlayerUuid,
                new_role: newRole
            }),
            success: function() {
                console.log("Role changed successfully");
            },
            error: function(xhr) {
                alert("Failed to change role: " + xhr.responseText);
            }
        });
    };

    PlayersPanel.prototype._createColorButton = function(playerJson) {
        var self = this;
        var button = $("<button>", {
            "class": "btn btn-xs btn-default change-color-btn",
            "text": "Color",
            "title": "Change player color",
            "data-player-uuid": playerJson["uuid"],
            "data-player-name": playerJson["name"]
        });

        button.on("click", function(e) {
            e.preventDefault();
            // Read the entry at click time: the color may have changed since
            // the button was made
            var $entry = self.$playersPanel.find("#" + playerJson["uuid"]);
            self._showColorChangeDialog(self._playerJsonFromEntry($entry));
        });

        return button;
    };

    PlayersPanel.prototype._showColorChangeDialog = function(playerJson) {
        var self = this;

        var dialogHtml = '<div class="role-change-dialog color-change-dialog">';
        dialogHtml += '<p>Change color for <strong class="player-name-display"></strong></p>';
        dialogHtml += '<select class="form-control color-select"></select>';
        dialogHtml += '<div class="m-t-s">';
        dialogHtml += '<button class="btn btn-primary btn-sm confirm-color-change">Confirm</button> ';
        dialogHtml += '<button class="btn btn-default btn-sm cancel-color-change">Cancel</button>';
        dialogHtml += '</div>';
        dialogHtml += '</div>';

        var $dialog = $(dialogHtml);
        $dialog.find('.player-name-display').text(playerJson["name"]);
        var $select = $dialog.find('.color-select');
        COLORS.forEach(function(color) {
            if (color === "blank") {
                return;
            }
            $select.append($('<option>', {
                value: color,
                text: color,
                selected: color === playerJson["color"]
            }));
        });
        var $overlay = $('<div class="role-change-overlay"></div>');

        $('body').append($overlay);
        $('body').append($dialog);

        var close = function() {
            $dialog.remove();
            $overlay.remove();
        };

        $dialog.find('.confirm-color-change').on('click', function() {
            var newColor = $select.val();
            if (newColor !== playerJson["color"]) {
                self._changeColor(playerJson["uuid"], newColor);
            }
            close();
        });
        $dialog.find('.cancel-color-change').on('click', close);
        $overlay.on('click', close);
    };

    PlayersPanel.prototype._changeColor = function(targetPlayerUuid, newColor) {
        $.ajax({
            url: "/api/color",
            type: "PUT",
            contentType: "application/json",
            data: JSON.stringify({
                room: window.sessionStorage.getItem("room"),
                target_player_uuid: targetPlayerUuid,
                color: newColor
            }),
            error: function(xhr) {
                alert("Failed to change color: " + xhr.responseText);
            }
        });
    };

    PlayersPanel.prototype._createKickButton = function(playerJson) {
        var self = this;
        var button = $("<button>", {
            "class": "btn btn-xs btn-danger kick-player-btn",
            "text": "Kick",
            "title": "Remove player from room",
            "data-player-uuid": playerJson["uuid"],
            "data-player-name": playerJson["name"]
        });
        
        button.on("click", function(e) {
            e.preventDefault();
            self._showKickConfirmDialog(playerJson);
        });
        
        return button;
    };

    PlayersPanel.prototype._showKickConfirmDialog = function(playerJson) {
        var self = this;
        
        var dialogHtml = '<div class="kick-confirm-dialog">';
        dialogHtml += '<p>Are you sure you want to kick <strong class="player-name-display"></strong>?</p>';
        dialogHtml += '<div class="m-t-s">';
        dialogHtml += '<button class="btn btn-danger btn-sm confirm-kick">Kick</button> ';
        dialogHtml += '<button class="btn btn-default btn-sm cancel-kick">Cancel</button>';
        dialogHtml += '</div>';
        dialogHtml += '</div>';
        
        var $dialog = $(dialogHtml);
        $dialog.find('.player-name-display').text(playerJson["name"]);
        var $overlay = $('<div class="kick-confirm-overlay"></div>');
        
        $('body').append($overlay);
        $('body').append($dialog);
        
        // Handle confirm
        $dialog.find('.confirm-kick').on('click', function() {
            self._kickPlayer(playerJson["uuid"]);
            $dialog.remove();
            $overlay.remove();
        });
        
        // Handle cancel
        $dialog.find('.cancel-kick').on('click', function() {
            $dialog.remove();
            $overlay.remove();
        });
        
        // Close on overlay click
        $overlay.on('click', function() {
            $dialog.remove();
            $overlay.remove();
        });
    };

    PlayersPanel.prototype._kickPlayer = function(targetPlayerUuid) {
        var roomUuid = window.sessionStorage.getItem("room");
        
        $.ajax({
            url: "/api/remove-player",
            type: "POST",
            contentType: "application/json",
            data: JSON.stringify({
                room: roomUuid,
                target_player_uuid: targetPlayerUuid
            }),
            success: function() {
                console.log("Player kicked successfully");
            },
            error: function(xhr) {
                alert("Failed to kick player: " + xhr.responseText);
            }
        });
    };

    PlayersPanel.prototype._createAssignCounterButton = function(counterPlayerJson) {
        var self = this;
        var button = $("<button>", {
            "class": "btn btn-xs btn-info assign-counter-btn",
            "text": "Assign",
            "title": "Assign counter to monitor a player",
            "data-counter-uuid": counterPlayerJson["uuid"],
            "data-counter-name": counterPlayerJson["name"]
        });
        
        button.on("click", function(e) {
            e.preventDefault();
            self._showCounterAssignmentDialog(counterPlayerJson);
        });
        
        return button;
    };

    PlayersPanel.prototype._showCounterAssignmentDialog = function(counterPlayerJson) {
        var self = this;

        // Colors claim squares, so counters count a color
        var groups = this.getColorGroups();
        if (groups.length === 0) {
            alert("No players to count yet. Counters count the colors players are using.");
            return;
        }

        var dialogHtml = '<div class="counter-assignment-dialog">';
        dialogHtml += '<p><strong class="counter-name-display"></strong> counts:</p>';
        dialogHtml += '<select class="form-control player-select"></select>';
        dialogHtml += '<div class="m-t-s">';
        dialogHtml += '<button class="btn btn-primary btn-sm confirm-assignment">Confirm</button> ';
        dialogHtml += '<button class="btn btn-default btn-sm cancel-assignment">Cancel</button>';
        dialogHtml += '</div>';
        dialogHtml += '</div>';

        var $dialog = $(dialogHtml);
        $dialog.find('.counter-name-display').text(counterPlayerJson["name"]);
        var $select = $dialog.find('.player-select');
        $select.append($('<option>', {value: 'null', text: '-- Nobody --'}));
        groups.forEach(function(group) {
            $select.append($('<option>', {
                value: group.color,
                text: group.label === group.color ? group.color : group.label + ' (' + group.color + ')',
                selected: group.color === counterPlayerJson.monitoring_color
            }));
        });
        var $overlay = $('<div class="counter-assignment-overlay"></div>');
        
        $('body').append($overlay);
        $('body').append($dialog);
        
        // Handle confirm
        $dialog.find('.confirm-assignment').on('click', function() {
            var color = $dialog.find('.player-select').val();
            self._assignCounter(counterPlayerJson["uuid"], color === 'null' ? null : color);
            $dialog.remove();
            $overlay.remove();
        });
        
        // Handle cancel
        $dialog.find('.cancel-assignment').on('click', function() {
            $dialog.remove();
            $overlay.remove();
        });
        
        // Close on overlay click
        $overlay.on('click', function() {
            $dialog.remove();
            $overlay.remove();
        });
    };

    PlayersPanel.prototype._assignCounter = function(counterPlayerUuid, color) {
        var roomUuid = window.sessionStorage.getItem("room");

        $.ajax({
            url: "/api/assign-counter",
            type: "POST",
            contentType: "application/json",
            data: JSON.stringify({
                room: roomUuid,
                counter_player_uuid: counterPlayerUuid,
                monitored_color: color
            }),
            success: function() {
                console.log("Counter assigned successfully");
            },
            error: function(xhr) {
                alert("Failed to assign counter: " + xhr.responseText);
            }
        });
    };

    PlayersPanel.prototype.handleCounterAssignment = function(assignmentJson) {
        console.log("handleCounterAssignment called", assignmentJson);
        
        var counterPlayer = assignmentJson["counter_player"];
        var color = assignmentJson["monitored_color"];

        // Update the counter player's entry
        var $counterEntry = this.$playersPanel.find("#" + counterPlayer["uuid"]);
        if (color) {
            $counterEntry.attr('data-monitoring-color', color);
        } else {
            $counterEntry.removeAttr('data-monitoring-color');
        }

        // Replace the assignment badge
        $counterEntry.find('.counter-assignment-badge').remove();
        if (color) {
            $counterEntry.find('.playername').after(this._counterBadge(assignmentJson["monitored_label"] || color));
        }
    };

    PlayersPanel.prototype._counterBadge = function(label) {
        return $("<span>", {
            "class": "counter-assignment-badge",
            "title": "Counting " + label,
            "text": " → " + label
        });
    };

    PlayersPanel.prototype.handleRoleChange = function(roleChangeJson) {
        console.log("handleRoleChange called", roleChangeJson);
        
        // Update the target player's display
        var targetPlayer = roleChangeJson["target_player"];
        this.setPlayer(targetPlayer);
        
        // Check if the current player's role changed
        if (targetPlayer["uuid"] === this.currentPlayer.uuid) {
            console.log("Current player is target, updating role from", this.currentPlayer.role, "to", targetPlayer["role"]);
            // The room page is laid out per role (counter panels, color
            // chooser, spectators can't mark), so load it again as the new role
            if (this.currentPlayer.role !== targetPlayer["role"]) {
                window.location.reload();
                return;
            }
        }
        
        // Also check if the actor's role changed (for GM transfers)
        var actor = roleChangeJson["player"];
        if (actor["uuid"] === this.currentPlayer.uuid) {
            console.log("Current player is actor, updating role from", this.currentPlayer.role, "to", actor["role"]);
            this.currentPlayer.role = actor["role"];
        }
        
        console.log("Current player role after update:", this.currentPlayer.role);
        
        // Refresh all management buttons for all players
        this._refreshAllManagementButtons();
        
        // Show notification
        var message = roleChangeJson["player"]["name"] + " changed " + 
                     targetPlayer["name"] + "'s role to " + 
                     roleChangeJson["new_role"];
        console.log(message);
    };

    PlayersPanel.prototype.removePlayer = function(playerJson) {
        var $playerEntry = this.$playersPanel.find("#" + playerJson["uuid"]);
        $playerEntry.remove();
        // Drop the Counters / Spectators section once it's empty
        this._removeEmptySections();
        this._notifyChange();
    };

    PlayersPanel.prototype.updateGoalCounters = function(board) {
        this.$playersPanel.find(".goalcounter").each(function() {
            var colorClass = $(this).attr('class').split(' ')[1];
            $(this).find(".squarecounter").html(board.getColorCount(colorClass));
            $(this).find(".rowcounter").html("(" + board.getRowCount(colorClass) + ")");
        });
    };

    return PlayersPanel;
})();
