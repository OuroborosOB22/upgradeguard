const status = document.getElementById("status");
const poll = setInterval(async () => {
  const response = await fetch(status.dataset.stateUrl);
  const data = await response.json();
  status.textContent = data.message || data.state;
  if (data.state === "finished" || data.state === "failed") {
    clearInterval(poll);
    location.reload();
  }
}, 1500);
