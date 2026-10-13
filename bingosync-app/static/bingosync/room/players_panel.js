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

    PlayersPanel.prototype._initializeExistingPlayers = function() {
        var self = this;
        
        // Process all existing player entries
        this.$playersPanel.find('.player-panel-entry').each(function() {
            var $playerEntry = $(this);
            var playerUuid = $playerEntry.attr('id');
            
            // Skip if buttons already exist
            if ($playerEntry.find('.role-change-btn, .kick-player-btn, .assign-counter-btn').length > 0) {
                return;
            }
            
            // Determine if this is the current player
            var isCurrentPlayer = playerUuid === self.currentPlayer.uuid;
            var isSpectator = $playerEntry.hasClass('spectator-entry');
            
            // Get player info from DOM
            var playerName = $playerEntry.find('.playername').text().trim();
            var $roleBadge = $playerEntry.find('.player-role-badge');
            var roleBadgeText = $roleBadge.text().trim();
            var isLoggedIn = $playerEntry.attr('data-is-logged-in') === 'true';
            var role = $playerEntry.attr('data-role') || 'player';
            var monitoringColor = $playerEntry.attr('data-monitoring-color') || null;
            
            // Determine role from badge if not in data attribute
            if (!$playerEntry.attr('data-role')) {
                if (roleBadgeText === '[GM]') {
                    role = 'gamemaster';
                } else if (roleBadgeText === '[C]') {
                    role = 'counter';
                } else if (roleBadgeText === '[S]') {
                    role = 'spectator';
                }
            }
            
            // Create player JSON object
            var playerJson = {
                uuid: playerUuid,
                name: playerName,
                role: role,
                is_logged_in: isLoggedIn,
                monitoring_color: monitoringColor
            };
            
            // Add management buttons if current player is gamemaster or counter
            if (self.currentPlayer.role === 'gamemaster') {
                var roleButton = self._createRoleButton(playerJson);
                $playerEntry.append(roleButton);
                
                // Add kick button (not for yourself)
                if (!isCurrentPlayer) {
                    var kickButton = self._createKickButton(playerJson);
                    $playerEntry.append(kickButton);
                }
                
                // Add counter assignment button for counters
                if (role === 'counter') {
                    var assignButton = self._createAssignCounterButton(playerJson);
                    $playerEntry.append(assignButton);
                }
            }
            // Counters pick who they count for with the "Counting for"
            // buttons above the board (counter.js), not a button here.
        });
    };

    PlayersPanel.prototype._refreshAllManagementButtons = function() {
        var self = this;
        
        console.log("_refreshAllManagementButtons called, current player role:", this.currentPlayer.role);
        
        // Remove all existing management buttons
        this.$playersPanel.find('.role-change-btn, .kick-player-btn, .assign-counter-btn').remove();
        
        // Re-add buttons if current player is gamemaster or counter
        if (this.currentPlayer.role === 'gamemaster') {
            console.log("Current player is gamemaster, adding buttons");
            this.$playersPanel.find('.player-panel-entry').each(function() {
                var $playerEntry = $(this);
                var playerUuid = $playerEntry.attr('id');
                var isCurrentPlayer = playerUuid === self.currentPlayer.uuid;
                
                // Get player info from DOM
                var playerName = $playerEntry.find('.playername').text().trim();
                var $roleBadge = $playerEntry.find('.player-role-badge');
                var roleBadgeText = $roleBadge.text().trim();
                var isLoggedIn = $playerEntry.attr('data-is-logged-in') === 'true';
                var role = $playerEntry.attr('data-role') || 'player';
                var monitoringColor = $playerEntry.attr('data-monitoring-color') || null;
                
                // Determine role from badge if not in data attribute
                if (!$playerEntry.attr('data-role')) {
                    if (roleBadgeText === '[GM]') {
                        role = 'gamemaster';
                    } else if (roleBadgeText === '[C]') {
                        role = 'counter';
                    } else if (roleBadgeText === '[S]') {
                        role = 'spectator';
                    }
                }
                
                // Create player JSON object
                var playerJson = {
                    uuid: playerUuid,
                    name: playerName,
                    role: role,
                    is_logged_in: isLoggedIn,
                    monitoring_color: monitoringColor
                };
                
                // Add management buttons
                var roleButton = self._createRoleButton(playerJson);
                $playerEntry.append(roleButton);
                
                // Add kick button (not for yourself)
                if (!isCurrentPlayer) {
                    var kickButton = self._createKickButton(playerJson);
                    $playerEntry.append(kickButton);
                }
                
                // Add counter assignment button for counters
                if (role === 'counter') {
                    var assignButton = self._createAssignCounterButton(playerJson);
                    $playerEntry.append(assignButton);
                }
            });
        } else {
            console.log("Current player is not gamemaster, buttons removed");
        }
    };

    PlayersPanel.prototype.setPlayer = function(playerJson) {
        var isSpectator = playerJson["role"] === "spectator";
        
        if(this.$playersPanel.find("#" + playerJson["uuid"]).length === 0) {
            // Player doesn't exist, insert them
            if (isSpectator) {
                this._addSpectator(playerJson);
            } else {
                this._addPlayer(playerJson);
            }
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
            
            // Check if role changed (e.g., player became spectator or vice versa)
            var wasSpectator = $playerEntry.hasClass("spectator-entry");
            if (isSpectator !== wasSpectator) {
                // Role changed between spectator and non-spectator, remove and re-add
                $playerEntry.remove();
                if (isSpectator) {
                    this._addSpectator(playerJson);
                } else {
                    this._addPlayer(playerJson);
                }
            } else {
                // Just update the existing entry
                if (!isSpectator) {
                    // Update color for non-spectators
                    var $playerGoalCounter = $playerEntry.find(".goalcounter");
                    COLORS.forEach(function(color) {
                        $playerGoalCounter.removeClass(getSquareColorClass(color));
                    });
                    $playerGoalCounter.addClass(getSquareColorClass(playerJson["color"]));
                }
                
                // Update role badge
                var $roleBadge = $playerEntry.find(".player-role-badge");
                $roleBadge.replaceWith(this._createRoleBadge(playerJson));
            }
        }
        this._notifyChange();
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
        
        // Add counter assignment badge if this is a counter counting a color
        if (playerJson["role"] === "counter" && playerJson["monitoring_color"]) {
            playerDiv.append(this._counterBadge(this.colorLabel(playerJson["monitoring_color"])));
        }
        
        // Add role management button if current player is gamemaster
        if (this.currentPlayer && this.currentPlayer.role === 'gamemaster') {
            var roleButton = this._createRoleButton(playerJson);
            playerDiv.append(roleButton);
            
            // Add kick button (but not for yourself)
            if (playerJson["uuid"] !== this.currentPlayer.uuid) {
                var kickButton = this._createKickButton(playerJson);
                playerDiv.append(kickButton);
            }
            
            // Add counter assignment button for counters
            if (playerJson["role"] === "counter") {
                var assignButton = this._createAssignCounterButton(playerJson);
                playerDiv.append(assignButton);
            }
        }

        // Insert before spectators section if it exists, otherwise at end
        var $spectatorsSection = this.$playersPanel.find(".spectators-section");
        if ($spectatorsSection.length > 0) {
            $spectatorsSection.before(playerDiv);
        } else {
            this.$playersPanel.append(playerDiv);
        }
    };

    PlayersPanel.prototype._addSpectator = function(playerJson) {
        var playerName = $("<span>", {"class": "playername", text: " " + playerJson["name"]});
        var roleBadge = this._createRoleBadge(playerJson);
        
        var spectatorDiv = $("<div>", {"id": playerJson["uuid"], "class": "player-panel-entry spectator-entry"});
        
        // Set data attributes
        spectatorDiv.attr('data-role', 'spectator');
        spectatorDiv.attr('data-is-logged-in', playerJson["is_logged_in"] ? 'true' : 'false');
        
        spectatorDiv.append(playerName);
        spectatorDiv.append(roleBadge);
        
        // Add role management button if current player is gamemaster
        if (this.currentPlayer && this.currentPlayer.role === 'gamemaster') {
            var roleButton = this._createRoleButton(playerJson);
            spectatorDiv.append(roleButton);
            
            // Add kick button for spectators
            var kickButton = this._createKickButton(playerJson);
            spectatorDiv.append(kickButton);
        }
        
        // Ensure spectators section exists
        var $spectatorsSection = this.$playersPanel.find(".spectators-section");
        if ($spectatorsSection.length === 0) {
            // Create spectators section
            $spectatorsSection = $("<div>", {"class": "spectators-section"});
            var header = $("<div>", {"class": "spectators-header", text: "Spectators"});
            $spectatorsSection.append(header);
            this.$playersPanel.append($spectatorsSection);
        }
        
        // Add spectator to the section
        $spectatorsSection.append(spectatorDiv);
    };

    PlayersPanel.prototype._createRoleBadge = function(playerJson) {
        var roleText = "";
        var roleTitle = "Role: " + playerJson["role"];
        
        if (playerJson["role"] === "gamemaster") {
            roleText = "[GM]";
        } else if (playerJson["role"] === "counter") {
            roleText = "[C]";
        } else if (playerJson["role"] === "spectator") {
            roleText = "[S]";
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
            $counterEntry.find('.player-role-badge').after(this._counterBadge(assignmentJson["monitored_label"] || color));
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
            // Update current player's role
            this.currentPlayer.role = targetPlayer["role"];
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
        var wasSpectator = $playerEntry.hasClass("spectator-entry");
        $playerEntry.remove();
        
        // If it was a spectator and spectators section is now empty (only header), remove the section
        if (wasSpectator) {
            var $spectatorsSection = this.$playersPanel.find(".spectators-section");
            if ($spectatorsSection.find(".spectator-entry").length === 0) {
                $spectatorsSection.remove();
            }
        }
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
