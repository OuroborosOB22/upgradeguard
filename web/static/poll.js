"use strict";
(function () {
  var status = document.getElementById("status");
  var log = document.getElementById("log");
  var lines = log.children.length;
  var timer = setInterval(function () {
    fetch(status.dataset.stateUrl).then(function (response) { return response.json(); }).then(function (data) {
      status.textContent = data.message || data.state;
      (data.log || []).slice(lines).forEach(function (line) {
        var item = document.createElement("li");
        item.textContent = line;
        log.appendChild(item);
      });
      lines = (data.log || []).length;
      if (data.state === "finished" || data.state === "failed") {
        clearInterval(timer);
        location.reload();
      }
    });
  }, 1500);
})();
