var BoardCover = (function(){
    "use strict";

    var BoardCover = function($boardContainer, hideCardInitially, boardRevealedUrl, cardRevealedUrl) {
        this.cardRevealedUrl = cardRevealedUrl;
        this.$boardContainer = $boardContainer;
        this.$boardCover = $boardContainer.find(".board-cover");
        this.boardRevealedUrl = boardRevealedUrl;

        this.setBoardHidden(hideCardInitially);

        var that = this;
        this.$boardCover.on("click", function() { that.onClick(); });
    };

    BoardCover.prototype.isBoardHidden = function() {
        return this.$boardContainer.hasClass("hidden-card");
    };

    BoardCover.prototype.setBoardHidden = function(hideBoard) {
        if (hideBoard) {
            this.$boardCover.show();
            this.$boardContainer.addClass("hidden-card");
        } else {
            this.$boardCover.hide();
            this.$boardContainer.removeClass("hidden-card");
        }
    };

    BoardCover.prototype.onClick = function() {
        if (!this.isBoardHidden()) {
            return;
        }
        // TODO: eliminate this injected global
        revealBoard();
        // Tell the server this player has uncovered their card, so their OBS
        // source uncovers too (the PUT below is the Gamemaster-only room reveal).
        $.ajax({
            "url": this.cardRevealedUrl,
            "type": "POST",
            "contentType": "application/json",
            "data": JSON.stringify({
                "room": window.sessionStorage.getItem("room"),
            }),
            "error": function(result) {
                console.log(result);
            }
        });
        $.ajax({
            "url": this.boardRevealedUrl,
            "type": "PUT",
            "data": JSON.stringify({
                "room": window.sessionStorage.getItem("room"),
            }),
            "error": function(result) {
                console.log(result);
            }
        });
    };

    return BoardCover;
})();

