/**
 * Counter UI for reviewing player claims
 */
var Counter = (function() {
    "use strict";

    var Counter = function(siteUrl, roomUuid, playerUuid, playerRole) {
        this.siteUrl = siteUrl;
        this.roomUuid = roomUuid;
        this.playerUuid = playerUuid;
        this.playerRole = playerRole;
        this.pendingClaims = {};
        this.claimHistory = [];
        if (this.playerRole === 'counter') this.initializeUI();
    };

    Counter.prototype.initializeUI = function() {
        this.$panel = $('#counter-panel');
        if (this.$panel.length === 0) return;
        this.$claimsList = this.$panel.find('#pending-claims-list');
        this.$historyList = this.$panel.find('#claim-history-list');
        this.updateClaimsList();
        this.updateHistoryList();
    };

    Counter.prototype.addPendingClaim = function(slot, playerName, goalName, claimStatus) {
        this.pendingClaims[slot] = { slot: slot, playerName: playerName, goalName: goalName, claimStatus: claimStatus };
        this.updateClaimsList();
        this.updateBoardIndicator(slot, claimStatus);
    };

    Counter.prototype.removeClaim = function(slot) {
        delete this.pendingClaims[slot];
        this.updateClaimsList();
        this.clearBoardIndicator(slot);
    };

    Counter.prototype.updateBoardIndicator = function(slot, status) {
        var $sq = $('#slot' + slot);
        $sq.removeClass('under-review');
        if (status === 'under_review') $sq.addClass('under-review');
    };

    Counter.prototype.clearBoardIndicator = function(slot) {
        $('#slot' + slot).removeClass('under-review');
    };

    Counter.prototype.addToHistory = function(slot, playerName, goalName, action, timestamp) {
        this.claimHistory.unshift({ slot: slot, playerName: playerName, goalName: goalName, action: action, timestamp: timestamp || new Date().toISOString() });
        if (this.claimHistory.length > 20) this.claimHistory = this.claimHistory.slice(0, 20);
        this.updateHistoryList();
    };

    Counter.prototype.updateHistoryList = function() {
        if (!this.$historyList) return;
        this.$historyList.empty();
        if (this.claimHistory.length === 0) {
            this.$historyList.append('<span class="history-placeholder">No claim history</span>');
            return;
        }
        var self = this;
        this.claimHistory.forEach(function(item) { self.$historyList.append(self.createHistoryItem(item)); });
    };

    Counter.prototype.createHistoryItem = function(item) {
        var icon, cls, hcls;
        switch(item.action) {
            case 'confirm': icon = '✓'; cls = 'text-success'; hcls = 'history-confirmed'; break;
            case 'reject': icon = '✗'; cls = 'text-danger'; hcls = 'history-rejected'; break;
            case 'under_review': icon = '⏳'; cls = 'text-warning'; hcls = 'history-under-review'; break;
            default: icon = '?'; cls = ''; hcls = '';
        }
        var time = new Date(item.timestamp).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});
        return '<div class="counter-history-item ' + hcls + '">' +
            '<span class="counter-history-action ' + cls + '">' + icon + '</span> ' +
            '<span class="counter-history-detail">' + item.goalName + '</span> ' +
            '<span class="counter-history-time">' + time + '</span></div>';
    };

    Counter.prototype.updateClaimsList = function() {
        if (!this.$claimsList) return;
        this.$claimsList.empty();
        var keys = Object.keys(this.pendingClaims);
        if (keys.length === 0) {
            this.$claimsList.append('<span class="history-placeholder">No pending claims</span>');
            return;
        }
        var self = this;
        keys.sort(function(a, b) { return parseInt(a) - parseInt(b); });
        keys.forEach(function(slot) { self.$claimsList.append(self.createClaimItem(self.pendingClaims[slot])); });
    };

    Counter.prototype.createClaimItem = function(claim) {
        var isReview = claim.claimStatus === 'under_review';
        var $item = $('<div class="counter-claim-item' + (isReview ? ' status-under-review' : '') + '"></div>');
        $item.append('<div class="counter-claim-goal" title="' + claim.goalName + '">' + claim.goalName + '</div>');
        $item.append('<div class="counter-claim-meta">' + claim.playerName + '</div>');

        var $actions = $('<div class="counter-claim-actions"></div>');
        var self = this;
        $('<button class="btn btn-xs btn-warning" title="Under Review">⏳</button>')
            .on('click', function() { self.reviewClaim(claim.slot, 'under_review'); }).appendTo($actions);
        $('<button class="btn btn-xs btn-success" title="Confirm">✓</button>')
            .on('click', function() { self.reviewClaim(claim.slot, 'confirm'); }).appendTo($actions);
        $('<button class="btn btn-xs btn-danger" title="Reject">✗</button>')
            .on('click', function() { self.reviewClaim(claim.slot, 'reject'); }).appendTo($actions);
        $item.append($actions);
        return $item;
    };

    Counter.prototype.reviewClaim = function(slot, action) {
        var self = this;
        var claim = this.pendingClaims[slot];
        $.ajax({
            url: this.siteUrl + '/api/review-claim',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ room: this.roomUuid, slot: slot, action: action }),
            success: function() { if (claim) self.addToHistory(slot, claim.playerName, claim.goalName, action); },
            error: function(xhr, s, e) { console.error('Failed to review claim:', e); }
        });
    };

    Counter.prototype.handleGoalEvent = function(event) {
        if (event.claim_status === 'pending_decision' && !event.remove) {
            this.addPendingClaim(parseInt(event.square.slot.replace('slot', '')), event.player.name, event.square.name, event.claim_status);
        }
    };

    Counter.prototype.handleClaimReviewEvent = function(event) {
        var slot = parseInt(event.square.slot.replace('slot', ''));
        if (event.action === 'confirm' || event.action === 'reject') {
            this.removeClaim(slot);
        } else if (event.action === 'under_review') {
            if (this.pendingClaims[slot]) {
                this.pendingClaims[slot].claimStatus = 'under_review';
                this.updateClaimsList();
                this.updateBoardIndicator(slot, 'under_review');
            }
        }
    };

    return Counter;
})();
