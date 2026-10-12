/**
 * Counter UI.
 *
 * - "Counting For" (above the board): one button per player, in their color
 *   and labelled with their name. Clicking one switches who you count for.
 * - Marks are approved by default. Right-clicking one of your player's goals
 *   puts it in review; right-clicking it again takes it back out. (For a
 *   counter this replaces starring goals.)
 * - The review list shows that player's goals in review, each with Approve
 *   (take it out of review) and Reject (remove the mark).
 *
 * The review list is derived from the board's squares, so it stays in step
 * with live updates and survives a page reload.
 */
var Counter = (function() {
    "use strict";

    var IN_REVIEW = ['under_review', 'pending_decision'];

    var HISTORY_STYLES = {
        under_review: {icon: '⏳', text: 'text-warning', item: 'history-under-review', label: 'In review'},
        confirm: {icon: '✓', text: 'text-success', item: 'history-confirmed', label: 'Approved'},
        reject: {icon: '✗', text: 'text-danger', item: 'history-rejected', label: 'Rejected'}
    };

    var Counter = function(roomUuid, counterJson, board, playersPanel) {
        this.roomUuid = roomUuid;
        this.counterUuid = counterJson.uuid;
        this.monitoringUuid = counterJson.monitoring_player_uuid || null;
        this.board = board;
        this.playersPanel = playersPanel;
        this.history = [];

        this.$targets = $('#counter-target-chooser .counter-targets');
        this.$reviewList = $('#pending-claims-list');
        this.$historyList = $('#claim-history-list');

        var that = this;
        board.onSquareRightClick = function(slot) { that.toggleReview(slot); };
        playersPanel.onChange = function() { that.renderTargets(); };

        this.renderTargets();
        this.renderReviewList();
        this.renderHistory();
    };

    // --- Counting For ---------------------------------------------------

    Counter.prototype.renderTargets = function() {
        var that = this;
        var players = this.playersPanel.getPlayers();
        this.$targets.empty();
        if (players.length === 0) {
            this.$targets.append($('<span>', {"class": "history-placeholder", text: "No players in the room yet"}));
            return;
        }
        players.forEach(function(player) {
            var chosen = player.uuid === that.monitoringUuid;
            $('<div>', {
                "class": "btn color-chooser counter-target " + getSquareColorClass(player.color) + (chosen ? " chosen-color" : ""),
                "title": chosen ? "Counting for " + player.name : "Count for " + player.name,
                "text": player.name
            }).on("click", function() { that.countFor(player.uuid); }).appendTo(that.$targets);
        });
    };

    Counter.prototype.countFor = function(playerUuid) {
        if (playerUuid === this.monitoringUuid) {
            return;
        }
        $.ajax({
            url: "/api/assign-counter",
            type: "POST",
            contentType: "application/json",
            data: JSON.stringify({
                room: this.roomUuid,
                counter_player_uuid: this.counterUuid,
                monitored_player_uuid: playerUuid
            }),
            error: function(xhr) { alert("Couldn't switch players: " + xhr.responseText); }
        });
    };

    // The assignment broadcast confirms the switch (also when the Gamemaster
    // reassigns this counter).
    Counter.prototype.handleCounterAssignment = function(json) {
        if (json.counter_player.uuid !== this.counterUuid) {
            return;
        }
        this.monitoringUuid = json.monitored_player ? json.monitored_player.uuid : null;
        this.renderTargets();
        this.renderReviewList();
    };

    // --- Review ---------------------------------------------------------

    Counter.prototype.toggleReview = function(slot) {
        var square = this.board.squares[slot - 1];
        // Only goals marked by the player you're counting for
        if (!square || !this.monitoringUuid || square.claimedBy !== this.monitoringUuid) {
            return;
        }
        if (IN_REVIEW.indexOf(square.claimStatus) !== -1) {
            this.review(slot, 'confirm');
        } else if (square.claimStatus === 'confirmed') {
            this.review(slot, 'under_review');
        }
    };

    Counter.prototype.review = function(slot, action) {
        var that = this;
        var goal = this.goalName(slot);
        $.ajax({
            url: "/api/review-claim",
            type: "POST",
            contentType: "application/json",
            data: JSON.stringify({room: this.roomUuid, slot: slot, action: action}),
            success: function() { that.addHistory(goal, action); },
            error: function(xhr) { console.error("Review failed:", xhr.responseText); }
        });
    };

    Counter.prototype.goalName = function(slot) {
        return this.board.squares[slot - 1].$square.children('.text-container').text();
    };

    // Called after any change to the board (marks, reviews, a new card).
    Counter.prototype.onBoardChanged = function() {
        this.renderReviewList();
    };

    Counter.prototype.renderReviewList = function() {
        var that = this;
        this.$reviewList.empty();
        if (!this.monitoringUuid) {
            this.$reviewList.append($('<span>', {"class": "history-placeholder", text: "Choose who you're counting for above the board."}));
            return;
        }
        var slots = [];
        this.board.squares.forEach(function(square, i) {
            if (square.claimedBy === that.monitoringUuid && IN_REVIEW.indexOf(square.claimStatus) !== -1) {
                slots.push(i + 1);
            }
        });
        if (slots.length === 0) {
            this.$reviewList.append($('<span>', {"class": "history-placeholder", text: "Nothing in review. Right-click one of their goals to review it."}));
            return;
        }
        slots.forEach(function(slot) { that.$reviewList.append(that.reviewItem(slot)); });
    };

    Counter.prototype.reviewItem = function(slot) {
        var that = this;
        var goal = this.goalName(slot);
        var $item = $('<div class="counter-claim-item status-under-review"></div>');
        $('<div class="counter-claim-goal"></div>').text(goal).attr('title', goal).appendTo($item);
        var $actions = $('<div class="counter-claim-actions"></div>').appendTo($item);
        $('<button class="btn btn-xs btn-success" title="Approve (take it out of review)">✓</button>')
            .on('click', function() { that.review(slot, 'confirm'); }).appendTo($actions);
        $('<button class="btn btn-xs btn-danger" title="Reject (removes the mark)">✗</button>')
            .on('click', function() { that.review(slot, 'reject'); }).appendTo($actions);
        return $item;
    };

    // --- History (this session's own actions) ---------------------------

    Counter.prototype.addHistory = function(goal, action) {
        this.history.unshift({goal: goal, action: action, time: new Date()});
        this.history = this.history.slice(0, 20);
        this.renderHistory();
    };

    Counter.prototype.renderHistory = function() {
        this.$historyList.empty();
        if (this.history.length === 0) {
            this.$historyList.append($('<span>', {"class": "history-placeholder", text: "No reviews yet"}));
            return;
        }
        var that = this;
        this.history.forEach(function(entry) {
            var style = HISTORY_STYLES[entry.action];
            var $item = $('<div class="counter-history-item"></div>').addClass(style.item);
            $('<span class="counter-history-action"></span>').addClass(style.text).text(style.icon).attr('title', style.label).appendTo($item);
            $item.append(' ');
            $('<span class="counter-history-detail"></span>').text(entry.goal).appendTo($item);
            $item.append(' ');
            $('<span class="counter-history-time"></span>')
                .text(entry.time.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})).appendTo($item);
            that.$historyList.append($item);
        });
    };

    return Counter;
})();
