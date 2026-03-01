var PlayersPanel = (function(){
    "use strict";

    var PlayersPanel = function($playersPanel, currentPlayer){
        this.$playersPanel = $playersPanel;
        this.currentPlayer = currentPlayer;
    };

    PlayersPanel.prototype.setPlayer = function(playerJson) {
        if(this.$playersPanel.find("#" + playerJson["uuid"]).length === 0) {
            // insert if the uuid is not already listed
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

            this.$playersPanel.insertOnce(playerDiv, function($possibleNext) {
                var possibleNextName = $.trim($possibleNext.find(".playername").text()).toLowerCase();
                return possibleNextName > playerJson["name"].toLowerCase();
            });
        } else {
            // otherwise update the player's color
            var $playerEntry = this.$playersPanel.find("#" + playerJson["uuid"]);
            var $playerGoalCounter = $playerEntry.find(".goalcounter");
            COLORS.forEach(function(color) {
                $playerGoalCounter.removeClass(getSquareColorClass(color));
            });
            $playerGoalCounter.addClass(getSquareColorClass(playerJson["color"]));
            
            // Update role badge
            var $roleBadge = $playerEntry.find(".player-role-badge");
            $roleBadge.replaceWith(this._createRoleBadge(playerJson));
        }
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
        
        // Position dialog
        $dialog.css({
            position: 'fixed',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            backgroundColor: 'white',
            padding: '20px',
            border: '1px solid #ccc',
            borderRadius: '4px',
            zIndex: 10001,
            minWidth: '300px'
        });
        
        $overlay.css({
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0,0,0,0.5)',
            zIndex: 10000
        });
        
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
        this.$playersPanel.find("#" + playerJson["uuid"]).remove();
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
