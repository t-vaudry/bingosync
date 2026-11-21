/**
 * Commentator UI: a read-only table of every counter's goal counts, one column
 * per player (the color a counter counts), one row per counted goal.
 *
 * Commentators see the board and everyone's marks like any other role but
 * can't mark; this adds the counters' numbers, which the server only shares
 * with commentators (/api/commentator-counts). Counts aren't broadcast, so
 * they're polled, and re-read whenever the board changes.
 */
var Commentator = (function() {
    "use strict";

    var POLL_MS = 5000;

    var Commentator = function(roomUuid, board) {
        this.roomUuid = roomUuid;
        this.board = board;
        this.$body = $('#commentator-counts .commentator-counts-body');
        this.data = null;
        this.loading = false;
        this.stale = false;

        var that = this;
        window.setInterval(function() {
            if (!document.hidden) {
                that.load();
            }
        }, POLL_MS);
        this.load();
    };

    Commentator.prototype.onBoardChanged = function() {
        // The goal names (and, for a new card, the goals) may have changed
        this.render();
        this.load();
    };

    Commentator.prototype.load = function() {
        if (this.loading) {
            // Read again once this answer is in, so a change isn't missed
            this.stale = true;
            return;
        }
        this.loading = true;
        var that = this;
        $.ajax({
            url: "/api/commentator-counts",
            type: "GET",
            data: {room: this.roomUuid}
        }).done(function(data) {
            that.data = data;
            that.render();
        }).fail(function(xhr) {
            console.error("Couldn't load counts:", xhr.responseText);
        }).always(function() {
            that.loading = false;
            if (that.stale) {
                that.stale = false;
                that.load();
            }
        });
    };

    Commentator.prototype.goalName = function(slot) {
        var square = this.board.squares[slot - 1];
        return square ? square.$square.children('.text-container').text() : '';
    };

    Commentator.prototype.render = function() {
        var data = this.data;
        this.$body.empty();
        if (!data || data.tallies.length === 0) {
            $('<div class="commentator-counts-empty">No counts yet.</div>').appendTo(this.$body);
            return;
        }

        // A row for each counted goal, and for each goal a counter has
        // marked complete without a count
        var slots = Object.keys(data.goals).map(Number);
        data.tallies.forEach(function(tally) {
            tally.completed.forEach(function(slot) {
                if (slots.indexOf(slot) === -1) {
                    slots.push(slot);
                }
            });
        });
        slots.sort(function(a, b) { return a - b; });

        // Say who counted when a color has more than one counter
        var perColor = {};
        data.tallies.forEach(function(tally) {
            perColor[tally.color] = (perColor[tally.color] || 0) + 1;
        });

        var $table = $('<table class="commentator-counts-table"></table>');
        var $head = $('<tr></tr>').append('<th class="commentator-goal-col">Goal</th>').appendTo($('<thead></thead>').appendTo($table));
        data.tallies.forEach(function(tally) {
            var $th = $('<th class="commentator-player-col"></th>')
                .attr('title', 'Counted by ' + tally.counter);
            $('<span class="commentator-player-name"></span>')
                .addClass(getSquareColorClass(tally.color)).text(tally.label).appendTo($th);
            if (perColor[tally.color] > 1) {
                $('<div class="commentator-counter-name"></div>').text(tally.counter).appendTo($th);
            }
            $head.append($th);
        });

        var that = this;
        var $tbody = $('<tbody></tbody>').appendTo($table);
        slots.forEach(function(slot) {
            var goal = data.goals[slot];
            var $row = $('<tr></tr>').append($('<td class="commentator-goal-col"></td>').text(that.goalName(slot)));
            data.tallies.forEach(function(tally) {
                var $cell = $('<td class="commentator-count"></td>');
                if (goal) {
                    var count = tally.counts[slot] || 0;
                    $cell.text(count + '/' + goal.amount)
                        .toggleClass('commentator-count-done', count >= goal.amount)
                        .toggleClass('commentator-count-zero', count === 0);
                } else if (tally.completed.indexOf(slot) !== -1) {
                    $cell.text('✔').addClass('commentator-count-done');
                } else {
                    $cell.text('–').addClass('commentator-count-zero');
                }
                $row.append($cell);
            });
            $tbody.append($row);
        });
        this.$body.append($table);
    };

    return Commentator;
})();
