COLORS = ["blank", "red", "blue", "green", "purple", "orange", "navy", "teal", "pink", "forest", "yellow"];

function getSquareColorClass(color) {
    return color + "square";
}

function getPlayerColorClass(color) {
    return color + "player";
}

function preciseSqrt(num) {
    const result = Math.sqrt(num);
    if (result * result !== num) {
        throw new Error("Number is not a square");
    }
    return result;
}

// The seed as shown to this viewer. In a room run by a Gamemaster the server
// sends null to players and spectators.
function seedText(seed) {
    return (seed === null || seed === undefined) ? "Hidden" : seed;
}

// global variables that are overwritten in bingosync.html main
var ROOM_SETTINGS = null;
var refreshBoard = function () {};
var hideBoard = function() {};
var revealBoard = function() {};
