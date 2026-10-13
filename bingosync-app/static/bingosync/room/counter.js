/**
 * Counter UI. Colors claim squares; players are associated with a color, so
 * a counter counts a color.
 *
 * - "Counting For" (above the board): one button per color in use, labelled
 *   with its player's name when exactly one player has it, otherwise with
 *   the color's name. Clicking one switches the color you count (and you
 *   take on that color).
 * - Marks are approved by default. Right-clicking a goal of your color puts
 *   it in review. (For a counter this replaces starring goals.)
 * - How a goal in review is approved or rejected on the board follows the
 *   counter's review style (a profile preference):
 *     list    - right-click again approves (the default)
 *     click   - left-click rejects, right-click approves
 *     hover   - a reject button shows on hover, right-click approves
 *     buttons - approve and reject buttons stay on the goal; right-click
 *               does nothing more
 * - The review list shows your color's goals in review, each with Approve
 *   (take it out of review) and Reject (remove the mark), whatever the style.
 *
 * The review list is derived from the board's squares, so it stays in step
 * with live updates and survives a page reload.
 *
 * Goal counts ("3/6 Gnomes") are private to this counter, kept on the server
 * per game and color (/api/counter-counts):
 * - Goals that take more than one step, or that also count toward other
 *   goals, get a [-] 3/6 [+] strip that fills like a progress bar in the
 *   counted color. Counting a goal moves the goals it triggers along with
 *   it (the server works that out).
 * - A ⚠ shows on a goal of your color that was marked before you counted it
 *   complete. Click it to dismiss it; it also goes once the count is
 *   complete or the goal is in review. Load brings dismissed alerts back.
 * - Save / Load / Clear / Reset in the panel: Load goes back to the saved
 *   counts when the runner loses in-game progress.
 */
var Counter = (function() {
    "use strict";

    var IN_REVIEW = ['under_review', 'pending_decision'];

    var HISTORY_STYLES = {
        under_review: {icon: '⏳', text: 'text-warning', item: 'history-under-review', label: 'In review'},
        confirm: {icon: '✓', text: 'text-success', item: 'history-confirmed', label: 'Approved'},
        reject: {icon: '✗', text: 'text-danger', item: 'history-rejected', label: 'Rejected'}
    };

    var Counter = function(roomUuid, counterJson, board, playersPanel, reviewStyle) {
        this.roomUuid = roomUuid;
        this.reviewStyle = reviewStyle || 'list';
        this.counterUuid = counterJson.uuid;
        this.monitoringColor = counterJson.monitoring_color || null;
        this.board = board;
        this.playersPanel = playersPanel;
        this.history = [];

        this.$targets = $('#counter-target-chooser .counter-targets');
        this.$reviewList = $('#pending-claims-list');
        this.$historyList = $('#claim-history-list');
        this.$countActions = $('#goal-count-actions');
        this.$savedAt = $('#goal-count-saved-at');

        // The server's copy of the counts; requests go one at a time so
        // quick clicks apply in order.
        this.tally = null;
        this.tallyGeneration = null;
        this.countQueue = $.when();

        var that = this;
        board.onSquareRightClick = function(slot) { that.onRightClick(slot); };
        board.onSquareClick = function(slot) { return that.onLeftClick(slot); };
        playersPanel.onChange = function() { that.renderTargets(); };

        this.$countActions.on('click', 'button[data-action]', function() {
            that.onCountAction($(this).data('action'));
        });

        this.renderTargets();
        this.renderReviewList();
        this.renderHistory();
        this.renderCountActions();
    };

    // --- Counting For ---------------------------------------------------

    Counter.prototype.renderTargets = function() {
        var that = this;
        var groups = this.playersPanel.getColorGroups();
        // Keep the color you're counting listed even once nobody's using it
        if (this.monitoringColor && !groups.some(function(g) { return g.color === that.monitoringColor; })) {
            groups.push({color: this.monitoringColor, label: this.monitoringColor, players: []});
        }
        this.$targets.empty();
        if (groups.length === 0) {
            this.$targets.append($('<span>', {"class": "history-placeholder", text: "No players in the room yet"}));
            return;
        }
        groups.forEach(function(group) {
            var chosen = group.color === that.monitoringColor;
            var who = group.players.length > 1 ? " (" + group.players.join(", ") + ")" : "";
            $('<div>', {
                "class": "btn color-chooser counter-target " + getSquareColorClass(group.color) + (chosen ? " chosen-color" : ""),
                "title": (chosen ? "Counting " : "Count ") + group.label + who,
                "text": group.label
            }).on("click", function() { that.countColor(group.color); }).appendTo(that.$targets);
        });
    };

    Counter.prototype.countColor = function(color) {
        if (color === this.monitoringColor) {
            return;
        }
        $.ajax({
            url: "/api/assign-counter",
            type: "POST",
            contentType: "application/json",
            data: JSON.stringify({
                room: this.roomUuid,
                counter_player_uuid: this.counterUuid,
                monitored_color: color
            }),
            error: function(xhr) { alert("Couldn't switch colors: " + xhr.responseText); }
        });
    };

    // The assignment broadcast confirms the switch (also when the Gamemaster
    // reassigns this counter).
    Counter.prototype.handleCounterAssignment = function(json) {
        if (json.counter_player.uuid !== this.counterUuid) {
            return;
        }
        this.monitoringColor = json.monitored_color || null;
        this.renderTargets();
        this.renderReviewList();
        // Each color has its own counts
        this.loadCounts();
    };

    // --- Review ---------------------------------------------------------

    Counter.prototype.hasMyColor = function(square) {
        return !!this.monitoringColor && square.colors.indexOf(this.monitoringColor) !== -1;
    };

    // A goal of the color you're counting (whoever marked it) that's in review
    Counter.prototype.isMyGoalInReview = function(square) {
        return !!square && this.hasMyColor(square) && IN_REVIEW.indexOf(square.claimStatus) !== -1;
    };

    Counter.prototype.onRightClick = function(slot) {
        var square = this.board.squares[slot - 1];
        if (!square || !this.hasMyColor(square)) {
            return;
        }
        if (IN_REVIEW.indexOf(square.claimStatus) !== -1) {
            // With buttons on the goal, a second right-click doesn't approve
            if (this.reviewStyle !== 'buttons') {
                this.review(slot, 'confirm');
            }
        } else if (square.claimStatus === 'confirmed') {
            this.review(slot, 'under_review');
        }
    };

    // Returns true when the click was a review action (so the board doesn't
    // treat it as marking the goal).
    Counter.prototype.onLeftClick = function(slot) {
        if (this.reviewStyle === 'click' && this.isMyGoalInReview(this.board.squares[slot - 1])) {
            this.review(slot, 'reject');
            return true;
        }
        return false;
    };

    // The "hover" and "buttons" styles put review buttons on the goals
    Counter.prototype.renderSquareButtons = function() {
        var that = this;
        this.board.squares.forEach(function(square, i) {
            square.$square.children('.review-actions').remove();
            if (that.reviewStyle !== 'hover' && that.reviewStyle !== 'buttons') {
                return;
            }
            if (!that.isMyGoalInReview(square)) {
                return;
            }
            var slot = i + 1;
            var $actions = $('<div class="review-actions"></div>')
                .toggleClass('review-actions-hover', that.reviewStyle === 'hover')
                .appendTo(square.$square);
            if (that.reviewStyle === 'buttons') {
                that.squareButton('btn-success', '✓', 'Approve (take it out of review)', slot, 'confirm').appendTo($actions);
            }
            that.squareButton('btn-danger', '✗', 'Reject (removes the mark)', slot, 'reject').appendTo($actions);
        });
    };

    Counter.prototype.squareButton = function(btnClass, text, title, slot, action) {
        var that = this;
        return $('<button class="btn btn-xs"></button>').addClass(btnClass).text(text).attr('title', title)
            .on('click', function(ev) {
                // Not a click on the goal itself
                ev.stopPropagation();
                that.review(slot, action);
            });
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
        if (this.tallyGeneration !== this.board.generation) {
            // A newly loaded board (first load or a new card): its counts
            this.loadCounts();
        } else {
            // The strips are still on the squares; alerts follow the marks
            this.renderCounts();
        }
    };

    Counter.prototype.renderReviewList = function() {
        var that = this;
        this.renderSquareButtons();
        this.$reviewList.empty();
        if (!this.monitoringColor) {
            this.$reviewList.append($('<span>', {"class": "history-placeholder", text: "Choose what you're counting above the board."}));
            return;
        }
        var slots = [];
        this.board.squares.forEach(function(square, i) {
            if (that.hasMyColor(square) && IN_REVIEW.indexOf(square.claimStatus) !== -1) {
                slots.push(i + 1);
            }
        });
        if (slots.length === 0) {
            this.$reviewList.append($('<span>', {"class": "history-placeholder", text: "Nothing in review. Right-click one of your color's goals to review it."}));
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

    // --- Goal counts ----------------------------------------------------

    Counter.prototype.loadCounts = function() {
        var that = this;
        var generation = this.board.generation;
        this.tallyGeneration = generation;
        if (!this.monitoringColor) {
            this.tally = null;
            this.renderCounts();
            return;
        }
        this.countQueue = this.countQueue.then(function() {
            return $.ajax({
                url: "/api/counter-counts",
                type: "GET",
                data: {room: that.roomUuid}
            }).then(function(tally) {
                that.setTally(tally, generation);
            }, function(xhr) {
                console.error("Couldn't load counts:", xhr.responseText);
                return $.when();
            });
        });
    };

    Counter.prototype.sendCount = function(body) {
        var that = this;
        var generation = this.board.generation;
        body.room = this.roomUuid;
        this.countQueue = this.countQueue.then(function() {
            return $.ajax({
                url: "/api/counter-counts",
                type: "POST",
                contentType: "application/json",
                data: JSON.stringify(body)
            }).then(function(tally) {
                that.setTally(tally, generation);
            }, function(xhr) {
                // Usually a click that raced past a limit; show the truth
                console.error("Count failed:", xhr.responseText);
                that.loadCounts();
                return $.when();
            });
        });
    };

    Counter.prototype.setTally = function(tally, generation) {
        // Ignore an answer about a card that has since been replaced, or a
        // color you've since switched away from
        if (generation !== this.board.generation || tally.color !== this.monitoringColor) {
            return;
        }
        this.tally = tally;
        this.renderCounts();
    };

    Counter.prototype.countOf = function(slot) {
        return this.tally.counts[slot] || 0;
    };

    // Marked with your color and approved, but not counted complete (and
    // not dismissed). A goal in review shows ⏳ in this spot instead.
    Counter.prototype.needsAlert = function(square, slot, goal) {
        return this.hasMyColor(square) && square.claimStatus === 'confirmed'
            && this.countOf(slot) < goal.amount
            && this.tally.dismissed.indexOf(slot) === -1;
    };

    Counter.prototype.renderCounts = function() {
        var that = this;
        var hadStrips = this.board.$board.find('.goal-count').length;
        this.board.squares.forEach(function(square, i) {
            var slot = i + 1;
            square.$square.children('.goal-count, .count-alert').remove();
            square.$square.removeClass('has-goal-count');
            var goal = that.tally && that.tally.goals[slot];
            if (!goal) {
                return;
            }
            square.$square.addClass('has-goal-count');
            that.countStrip(slot, goal).appendTo(square.$square);
            if (that.needsAlert(square, slot, goal)) {
                $('<div class="count-alert">⚠</div>')
                    .attr('title', "Marked at " + that.countOf(slot) + "/" + goal.amount + ". Click to dismiss")
                    .on('click', function(ev) {
                        ev.stopPropagation();
                        that.sendCount({action: 'dismiss', slot: slot});
                    })
                    .appendTo(square.$square);
            }
        });
        // Goal text shrinks to fit above the strips (the strips only come and
        // go together, when counts are loaded for a card or a color)
        if (hadStrips !== this.board.$board.find('.goal-count').length) {
            this.board.refitGoalText();
        }
        this.renderCountActions();
    };

    Counter.prototype.countStrip = function(slot, goal) {
        var that = this;
        var count = this.countOf(slot);
        var $strip = $('<div class="goal-count"></div>');
        // Progress bar in the counted color, inset in the dark strip so it
        // shows on a goal already marked in that color
        $('<div class="goal-count-fill"></div>')
            .addClass(getSquareColorClass(this.monitoringColor))
            .css('width', (100 * count / goal.amount) + '%')
            .appendTo($('<div class="goal-count-track"></div>').appendTo($strip));
        var button = function(text, title, delta, enabled) {
            return $('<button type="button" class="goal-count-btn"></button>')
                .text(text).attr('title', title).prop('disabled', !enabled)
                .on('click', function(ev) {
                    // Not a click on the goal itself
                    ev.stopPropagation();
                    that.sendCount({action: 'change', slot: slot, delta: delta});
                });
        };
        button('−', 'Count one fewer', -1, count > 0).appendTo($strip);
        $('<span class="goal-count-value"></span>').text(count + '/' + goal.amount).appendTo($strip);
        button('+', 'Count one more', 1, count < goal.amount).appendTo($strip);
        // Clicks between the buttons aren't clicks on the goal either
        $strip.on('click', function(ev) { ev.stopPropagation(); });
        return $strip;
    };

    Counter.prototype.renderCountActions = function() {
        var ready = !!this.tally;
        var saved = ready && !!this.tally.saved_at;
        this.$countActions.find('button').prop('disabled', !ready);
        this.$countActions.find('[data-action=load], [data-action=clear]').prop('disabled', !saved);
        this.$savedAt.text(!ready ? '' : saved
            ? 'Saved ' + new Date(this.tally.saved_at).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})
            : 'Nothing saved');
    };

    Counter.prototype.onCountAction = function(action) {
        if (action === 'reset' && !confirm("Reset every count to zero and clear the saved state? This can't be undone.")) {
            return;
        }
        this.sendCount({action: action});
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
