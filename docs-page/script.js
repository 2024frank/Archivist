const buttons = document.querySelectorAll("[data-copy-target]");

buttons.forEach((button) => {
  button.addEventListener("click", async () => {
    const targetId = button.getAttribute("data-copy-target");
    const target = document.getElementById(targetId);
    if (!target) return;

    const originalText = button.textContent;
    await navigator.clipboard.writeText(target.textContent.trim());
    button.textContent = "Copied";

    window.setTimeout(() => {
      button.textContent = originalText;
    }, 1400);
  });
});
