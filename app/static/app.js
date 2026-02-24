/**
 * app.js — minimal vanilla JS for the PowerBuilding Workout Tracker.
 * Grows with each phase. No frameworks, no build step.
 */

// Auto-dismiss flash banners after 5 seconds
document.addEventListener('DOMContentLoaded', () => {
  const banners = document.querySelectorAll('[data-flash]');
  banners.forEach(banner => {
    setTimeout(() => {
      banner.style.transition = 'opacity 0.4s ease';
      banner.style.opacity = '0';
      setTimeout(() => banner.remove(), 400);
    }, 5000);
  });
});
