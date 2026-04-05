var ChatSocket = (function(){
    "use strict";

    var ChatSocket = function(chatPanel, board, playersPanel, socketsUrl, currentPlayer) {
        this.chatPanel = chatPanel;
        this.board = board;
        this.playersPanel = playersPanel;
        this.socketsUrl = socketsUrl;
        this.currentPlayer = currentPlayer;
    };

    ChatSocket.prototype.init = function(socketKey) {
        this.socketKey = socketKey;
        this.chatSocket = new WebSocket(this.socketsUrl);

        this.chatSocket.onopen = this.onSocketOpen.bind(this);
        this.chatSocket.onmessage = this.onSocketMessage.bind(this);
        this.chatSocket.onclose = this.onSocketClose.bind(this);
    };

    ChatSocket.prototype.onSocketOpen = function() {
        console.log("socket opened!");
        this.chatSocket.send(JSON.stringify({"socket_key": this.socketKey}));
    };

    ChatSocket.prototype.onSocketClose = function() {
        var disconnectText = "*** Disconnected from server, try refreshing.";
        var message = $("<div>", {"class": "connection-message", text: disconnectText}).toHtml();
        this.chatPanel.appendChatMessage(message);
    };

    ChatSocket.prototype.onSocketMessage = function(evt) {
        var json = JSON.parse(evt.data);
        if (json["type"] === "error") {
            console.log("Got error message from socket: ", json);
            return;
        } else if (json["type"] === "goal") {
            var square = this.board.getSquare(json["square"]["slot"]);
            square.setColors(json["square"]["colors"]);
            square.setClaimStatus(json["square"]["claim_status"] || null);
            this.playersPanel.updateGoalCounters(this.board);
            this.board.hideSquares();
            
            // If counter UI exists and claim needs review, notify it
            if (window.counterUI && json["claim_status"] === "pending_decision") {
                window.counterUI.handleGoalEvent(json);
            }
        }
        else if(json["type"] === "color") {
            this.playersPanel.setPlayer(json["player"]);
            this.playersPanel.updateGoalCounters(this.board);
        }
        else if(json["type"] === "connection") {
            if(json["event_type"] === "connected") {
                this.playersPanel.setPlayer(json["player"]);
                this.playersPanel.updateGoalCounters(this.board);
            }
            else if(json["event_type"] === "disconnected") {
                // Check if the disconnected player is the current user
                if(json["player"]["uuid"] === this.currentPlayer.uuid) {
                    // Current user was disconnected (e.g., room closed), redirect to landing page
                    var disconnectText = "*** You have been disconnected from the room.";
                    var message = $("<div>", {"class": "connection-message", text: disconnectText}).toHtml();
                    this.chatPanel.appendChatMessage(message);
                    
                    // Redirect after a short delay to show the message
                    setTimeout(function() {
                        window.location.href = "/";
                    }, 1500);
                } else {
                    // Another player disconnected, just remove them from the panel
                    this.playersPanel.removePlayer(json["player"]);
                }
            }
        }
        else if(json["type"] === "role_change") {
            this.playersPanel.handleRoleChange(json);
        }
        else if(json["type"] === "counter_assignment") {
            this.playersPanel.handleCounterAssignment(json);
        }
        else if(json["type"] === "claim_review") {
            // Handle claim review event — update colors and claim status for ALL clients
            var square = this.board.getSquare(json["square"]["slot"]);
            square.setColors(json["square"]["colors"]);
            square.setClaimStatus(json["square"]["claim_status"] || null);
            this.playersPanel.updateGoalCounters(this.board);
            this.board.hideSquares();
            
            // If counter UI exists, notify it
            if (window.counterUI) {
                window.counterUI.handleClaimReviewEvent(json);
            }
        }
        else if(json["type"] === "new-card") {
            // TODO: remove this external dependency
            // if the card was never revealed show what the seed was in the chat anyway
            $("#bingo-chat .new-card-message .seed-hidden").text(ROOM_SETTINGS.seed).removeClass('seed-hidden').addClass('seed');
            refreshBoard();
        } else if (json["type"] === "chat") {
            // no special effects for chat, it just gets written to the panel
        } else {
            console.log("unrecognized event type: ", json);
        }
        this.chatPanel.handleEvent(json);
    };


    return ChatSocket;
})();
