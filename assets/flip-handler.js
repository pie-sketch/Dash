document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll(".card-content").forEach(function (card) {
    card.addEventListener("click", function () {
      this.classList.toggle("flip-active");
    });
  });
});
