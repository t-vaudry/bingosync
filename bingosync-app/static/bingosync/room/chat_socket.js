var ChatSocket = (function(){
    "use strict";

    // Wait this long (doubling up to the max) before trying a dropped socket again
    var RECONNECT_MIN_MS = 1000;
    var RECONNECT_MAX_MS = 15000;

    var ChatSocket = function(chatPanel, board, playersPanel, socketsUrl, currentPlayer) {
        this.chatPanel = chatPanel;
        this.board = board;
        this.playersPanel = playersPanel;
        this.socketsUrl = socketsUrl;
        this.currentPlayer = currentPlayer;
        // Where to get a fresh socket key for a reconnect (a key only lives a
        // few minutes). Without it, a reconnect tries the old key again.
        this.socketKeyUrl = null;
        // Called each time the server confirms this page is registered for
        // the room's events, with whether it's a reconnect. This is when to
        // fetch whatever was missed while there was no socket.
        this.onRegistered = null;
        this.reconnectDelay = RECONNECT_MIN_MS;
        this.reconnectTimer = null;
        this.hasRegistered = false;
        this.noticeShown = false;
        this.gaveUp = false;
        // A key fetch for a reconnect is under way (so a second trigger can't
        // start another socket alongside it)
        this.reconnecting = false;
    };

    ChatSocket.prototype.init = function(socketKey) {
        var self = this;
        this.socketKey = socketKey;
        this.connect();
        // Coming back to the tab or the network is the moment to check
        // the socket is still there rather than wait out the backoff
        var checkNow = function() {
            if (!document.hidden) {
                self.reconnectNow();
            }
        };
        document.addEventListener('visibilitychange', checkNow);
        window.addEventListener('online', checkNow);
    };

    ChatSocket.prototype.connect = function() {
        this.reconnecting = false;
        var ws = new WebSocket(this.socketsUrl);
        this.chatSocket = ws;
        var self = this;
        ws.onopen = function() { if (ws === self.chatSocket) { self.onSocketOpen(); } };
        ws.onmessage = function(evt) { if (ws === self.chatSocket) { self.onSocketMessage(evt); } };
        ws.onclose = function() { if (ws === self.chatSocket) { self.onSocketClose(); } };
    };

    ChatSocket.prototype.onSocketOpen = function() {
        console.log("socket opened!");
        this.chatSocket.send(JSON.stringify({"socket_key": this.socketKey}));
    };

    ChatSocket.prototype.onSocketClose = function() {
        if (!this.noticeShown && this.chatPanel) {
            var disconnectText = "*** Disconnected from server, reconnecting...";
            var message = $("<div>", {"class": "connection-message", text: disconnectText}).toHtml();
            this.chatPanel.appendChatMessage(message);
            this.noticeShown = true;
        }
        this.scheduleReconnect();
    };

    ChatSocket.prototype.scheduleReconnect = function() {
        var self = this;
        if (this.gaveUp || this.reconnectTimer) {
            return;
        }
        this.reconnectTimer = setTimeout(function() {
            self.reconnectTimer = null;
            self.reconnect();
        }, this.reconnectDelay);
        this.reconnectDelay = Math.min(this.reconnectDelay * 2, RECONNECT_MAX_MS);
    };

    // Try now, if the socket isn't up
    ChatSocket.prototype.reconnectNow = function() {
        var open = this.chatSocket && (this.chatSocket.readyState === WebSocket.OPEN ||
                                       this.chatSocket.readyState === WebSocket.CONNECTING);
        if (open || this.reconnecting || this.gaveUp) {
            return;
        }
        clearTimeout(this.reconnectTimer);
        this.reconnectTimer = null;
        this.reconnect();
    };

    ChatSocket.prototype.reconnect = function() {
        var self = this;
        if (this.reconnecting) {
            return;
        }
        if (!this.socketKeyUrl) {
            this.connect();
            return;
        }
        this.reconnecting = true;
        $.ajax({url: this.socketKeyUrl, dataType: 'json', cache: false}).done(function(result) {
            self.socketKey = result["socket_key"];
            self.connect();
        }).fail(function(xhr) {
            self.reconnecting = false;
            if (xhr.status === 401 || xhr.status === 403 || xhr.status === 404) {
                // Not in this room any more (kicked, or left from another tab)
                self.gaveUp = true;
                if (self.chatPanel) {
                    var text = "*** You are no longer in this room.";
                    self.chatPanel.appendChatMessage($("<div>", {"class": "connection-message", text: text}).toHtml());
                }
                return;
            }
            self.scheduleReconnect();
        });
    };

    ChatSocket.prototype.onRegisteredByServer = function() {
        var isReconnect = this.hasRegistered;
        this.hasRegistered = true;
        this.reconnectDelay = RECONNECT_MIN_MS;
        if (this.noticeShown && this.chatPanel) {
            var text = "*** Reconnected.";
            this.chatPanel.appendChatMessage($("<div>", {"class": "connection-message", text: text}).toHtml());
        }
        this.noticeShown = false;
        if (this.onRegistered) {
            this.onRegistered(isReconnect);
        }
    };

    ChatSocket.prototype.onSocketMessage = function(evt) {
        var self = this;
        var json = JSON.parse(evt.data);
        if (json["type"] === "registered") {
            this.onRegisteredByServer();
            return;
        }
        if (json["type"] === "error") {
            console.log("Got error message from socket: ", json);
            // Most likely the socket key expired or was used up: close, and
            // the reconnect gets a fresh one
            if (this.chatSocket) {
                this.chatSocket.close();
            }
            return;
        } else if (json["type"] === "goal") {
            var square = this.board.getSquare(json["square"]["slot"]);
            square.setColors(json["square"]["colors"]);
            square.setClaim(json["square"]["claim_status"], json["square"]["claimed_by"]);
            if (this.playersPanel) { this.playersPanel.updateGoalCounters(this.board); }
            this.board.hideSquares();

            // An unmarked goal drops out of the counter's review list
            if (window.counterUI) {
                window.counterUI.onBoardChanged();
            }
            if (window.commentatorUI) {
                window.commentatorUI.load();
            }
        }
        else if(json["type"] === "color") {
            if (this.playersPanel) {
                this.playersPanel.setPlayer(json["player"]);
                this.playersPanel.updateGoalCounters(this.board);
            }
            // A Gamemaster changed our color: mark with it from now on, and
            // under fog of war see the board as the new color does
            var colorChooser = this.board && this.board.colorChooser;
            if (json["changed_by"] && this.currentPlayer &&
                    json["player"]["uuid"] === this.currentPlayer.uuid &&
                    colorChooser && colorChooser.setChosenColor) {
                this.currentPlayer.color = json["color"];
                colorChooser.defaultColor = json["color"];
                colorChooser.setChosenColor(json["color"]);
                this.board.hideSquares();
            }
        }
        else if(json["type"] === "revealed") {
            // The Gamemaster revealed the card for the room: uncover it here
            // too (a no-op on pages that have no cover).
            revealBoard();
            // Players and spectators only get the seed once it's revealed
            refreshSeed();
        }
        else if(json["type"] === "connection") {
            if (!this.playersPanel) {
                // nothing to show; the OBS page only cares about the board
            }
            else if(json["event_type"] === "connected") {
                this.playersPanel.setPlayer(json["player"]);
                this.playersPanel.updateGoalCounters(this.board);
            }
            else if(json["event_type"] === "disconnected") {
                // Check if the disconnected player is the current user
                if(json["player"]["uuid"] === this.currentPlayer.uuid) {
                    var leaveRoom = function() {
                        // Current user was disconnected (e.g., kicked), redirect to landing page
                        var disconnectText = "*** You have been disconnected from the room.";
                        var message = $("<div>", {"class": "connection-message", text: disconnectText}).toHtml();
                        self.chatPanel.appendChatMessage(message);

                        // Redirect after a short delay to show the message
                        setTimeout(function() {
                            window.location.href = "/";
                        }, 1500);
                    };
                    if (!this.socketKeyUrl) {
                        leaveRoom();
                    } else {
                        // Our page is here and listening, so a disconnect
                        // report can be a stale one (arriving after we came
                        // back). Only leave if the server no longer has us
                        // in the room; otherwise the list sets itself right.
                        $.ajax({url: this.socketKeyUrl, dataType: 'json', cache: false}).done(function() {
                            if (self.playersPanel) { self.playersPanel.scheduleReload(0); }
                        }).fail(function(xhr) {
                            if (xhr.status === 401 || xhr.status === 403 || xhr.status === 404) {
                                leaveRoom();
                            }
                        });
                    }
                } else {
                    // Another player disconnected, just remove them from the panel
                    this.playersPanel.removePlayer(json["player"]);
                }
            }
        }
        else if(json["type"] === "role_change") {
            if (this.playersPanel) { this.playersPanel.handleRoleChange(json); }
        }
        else if(json["type"] === "counter_assignment") {
            if (this.playersPanel) { this.playersPanel.handleCounterAssignment(json); }
            if (window.counterUI) {
                window.counterUI.handleCounterAssignment(json);
            }
        }
        else if(json["type"] === "claim_review") {
            // Handle claim review event — update colors and claim status for ALL clients
            var square = this.board.getSquare(json["square"]["slot"]);
            square.setColors(json["square"]["colors"]);
            square.setClaim(json["square"]["claim_status"], json["square"]["claimed_by"]);
            if (this.playersPanel) { this.playersPanel.updateGoalCounters(this.board); }
            this.board.hideSquares();

            if (window.counterUI) {
                window.counterUI.onBoardChanged();
            }
            if (window.commentatorUI) {
                window.commentatorUI.load();
            }
        }
        else if(json["type"] === "game_won") {
            if (window.showWinCelebration) {
                window.showWinCelebration(json["winner"], json["goals"]);
            }
        }
        else if(json["type"] === "new-card") {
            // TODO: remove this external dependency
            // if the card was never revealed show what the seed was in the chat anyway
            $("#bingo-chat .new-card-message .seed-hidden").text(seedText(ROOM_SETTINGS.seed)).removeClass('seed-hidden').addClass('seed');
            // Stars belong to one card; a new card starts with none
            this.board.setStars([]);
            refreshBoard();
        } else if (json["type"] === "chat") {
            // no special effects for chat, it just gets written to the panel
        } else {
            console.log("unrecognized event type: ", json);
        }
        if (this.chatPanel) { this.chatPanel.handleEvent(json); }
    };


    return ChatSocket;
})();
