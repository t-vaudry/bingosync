var PlayersPanel = (function(){
    "use strict";

    var PlayersPanel = function($playersPanel, currentPlayer){
        this.$playersPanel = $playersPanel;
        this.currentPlayer = currentPlayer;
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
    };

    PlayersPanel.prototype._addPlayer = function(playerJson) {
        var colorClass = getSquareColorClass(playerJson["color"]);
        var goalCounter = $("<span>", {"class": "goalcounter " + colorClass, html: "<span class=\"squarecounter\" title=\"Squares with color.\">0</span> <span class=\"rowcounter\" title=\"Rows with color.\">(0)</span>"});

        var playerName = $("<span>", {"class": "playername", text: " " + playerJson["name"]});
        
        // Add role badge
        var roleBadge = this._createRoleBadge(playerJson);
        
        var playerDiv = $("<div>", {"id": playerJson["uuid"], "class": "player-panel-entry"});
        playerDiv.append(goalCounter);
        playerDiv.append(playerName);
        playerDiv.append(roleBadge);
        
        // Add role management button if current player is gamemaster
        if (this.currentPlayer && this.currentPlayer.role === 'gamemaster') {
            var roleButton = this._createRoleButton(playerJson);
            playerDiv.append(roleButton);
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
        spectatorDiv.append(playerName);
        spectatorDiv.append(roleBadge);
        
        // Add role management button if current player is gamemaster
        if (this.currentPlayer && this.currentPlayer.role === 'gamemaster') {
            var roleButton = this._createRoleButton(playerJson);
            spectatorDiv.append(roleButton);
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
            roleText = playerJson["is_also_player"] ? "[GM+P]" : "[GM]";
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
        
        // Create role selection dialog
        var roles = [
            {value: "gamemaster", label: "Gamemaster"},
            {value: "player", label: "Player"},
            {value: "counter", label: "Counter"},
            {value: "spectator", label: "Spectator"}
        ];
        
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

    PlayersPanel.prototype.handleRoleChange = function(roleChangeJson) {
        // Update the target player's display
        var targetPlayer = roleChangeJson["target_player"];
        this.setPlayer(targetPlayer);
        
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
