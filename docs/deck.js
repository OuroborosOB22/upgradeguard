const slides = Array.from(document.querySelectorAll(".slide"));
const dotsHolder = document.getElementById("dots");
const progress = document.getElementById("progress");
const slideName = document.getElementById("slideName");
const prevButton = document.getElementById("prev");
const nextButton = document.getElementById("next");

let current = 0;

slides.forEach((slide, index) => {
  const dot = document.createElement("button");
  dot.className = "dot";
  dot.setAttribute("aria-label", "slide " + (index + 1));
  dot.addEventListener("click", () => goTo(index));
  dotsHolder.appendChild(dot);
});

const dots = Array.from(document.querySelectorAll(".dot"));

function goTo(index) {
  if (index < 0 || index >= slides.length) return;
  slides[current].classList.remove("is-active");
  current = index;
  slides[current].classList.add("is-active");
  dots.forEach((dot, position) => dot.classList.toggle("on", position === current));
  progress.style.width = ((current + 1) / slides.length) * 100 + "%";
  slideName.textContent = slides[current].dataset.name + " | " + (current + 1) + " of " + slides.length;
  prevButton.disabled = current === 0;
  nextButton.disabled = current === slides.length - 1;
  if (slides[current].querySelector("#flow")) startFlow();
}

prevButton.addEventListener("click", () => goTo(current - 1));
nextButton.addEventListener("click", () => goTo(current + 1));

document.addEventListener("keydown", (event) => {
  if (event.key === "ArrowRight" || event.key === " " || event.key === "PageDown") { event.preventDefault(); goTo(current + 1); }
  if (event.key === "ArrowLeft" || event.key === "PageUp") { event.preventDefault(); goTo(current - 1); }
  if (event.key === "Home") goTo(0);
  if (event.key === "End") goTo(slides.length - 1);
});

let touchStart = null;
document.addEventListener("touchstart", (event) => { touchStart = event.changedTouches[0].clientX; });
document.addEventListener("touchend", (event) => {
  if (touchStart === null) return;
  const shift = event.changedTouches[0].clientX - touchStart;
  if (Math.abs(shift) > 60) goTo(shift < 0 ? current + 1 : current - 1);
  touchStart = null;
});

const CASES = {
  safe: {
    line: 'upgrade <code>requests</code> from <code>2.28.2</code> to <code>2.32.5</code>',
    decision: "Accept",
    sub: "nothing broke, and it fixes known problems",
    tests: "0",
    vulns: "3",
    packages: "2",
    seconds: "12",
  },
  risky: {
    line: 'upgrade <code>jinja2</code> from <code>3.0.3</code> to <code>3.1.6</code>',
    decision: "Reject",
    sub: "5 tests passed before and fail after",
    tests: "5",
    vulns: "2",
    packages: "1",
    seconds: "12",
  },
};

let activeCase = "safe";
let timers = [];

const steps = [
  { selector: ".n1" }, { selector: ".a1" },
  { selector: ".n2" }, { selector: ".n3" }, { selector: ".a2" },
  { selector: ".n4" }, { selector: ".a3" },
  { selector: ".n5" }, { selector: ".a4" },
  { selector: ".n6" }, { selector: ".a5" },
  { selector: ".n7" },
];

function clearFlow() {
  timers.forEach((timer) => clearTimeout(timer));
  timers = [];
  document.querySelectorAll(".fnode, .farrow").forEach((node) => node.classList.remove("lit"));
  const verdictNode = document.getElementById("verdictNode");
  verdictNode.classList.remove("accept", "reject");
  document.getElementById("verdictText").textContent = "Verdict";
  document.getElementById("verdictSub").textContent = "with the evidence attached";
  document.getElementById("resultStrip").classList.remove("show");
}

function startFlow() {
  clearFlow();
  const data = CASES[activeCase];
  document.getElementById("caseline").innerHTML = data.line;

  steps.forEach((step, index) => {
    timers.push(setTimeout(() => {
      document.querySelector(step.selector).classList.add("lit");
    }, 260 + index * 230));
  });

  const settle = 260 + steps.length * 230 + 120;
  timers.push(setTimeout(() => {
    const verdictNode = document.getElementById("verdictNode");
    verdictNode.classList.add(data.decision.toLowerCase());
    document.getElementById("verdictText").textContent = data.decision;
    document.getElementById("verdictSub").textContent = data.sub;
    document.getElementById("rTests").textContent = data.tests;
    document.getElementById("rVuln").textContent = data.vulns;
    document.getElementById("rPkg").textContent = data.packages;
    document.getElementById("rTime").textContent = data.seconds;
    document.getElementById("resultStrip").classList.add("show");
  }, settle));
}

document.querySelectorAll(".case-btn").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".case-btn").forEach((other) => other.classList.remove("is-on"));
    button.classList.add("is-on");
    activeCase = button.dataset.case;
    startFlow();
  });
});

document.getElementById("replay").addEventListener("click", startFlow);

goTo(0);
