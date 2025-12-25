document.addEventListener("DOMContentLoaded", () => {
  console.log("🔥 design.js loaded");

  const nameInput = document.getElementById("name");
  const stem = document.querySelector(".stem-letters");

  function updateStem(name) {
    stem.innerHTML = "";

    if (!name) return;

    // IMPORTANT: split name into letters
    const letters = name.split("");

    // FIRST letter = anchor (bottom)
    letters.forEach((letter, index) => {
      const span = document.createElement("span");
      span.classList.add("stem-letter");

      if (index === 0) {
        span.classList.add("stem-start");
      }

      span.textContent = letter;
      stem.appendChild(span);
    });
  }

  nameInput.addEventListener("input", (e) => {
    updateStem(e.target.value.toLowerCase());
  });
});

