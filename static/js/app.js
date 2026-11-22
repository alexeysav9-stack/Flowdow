/**
 * Flowdow Frontend JavaScript
 */
document.addEventListener("DOMContentLoaded", function () {
  // Auto-dismiss alert notifications after 5 seconds
  const alerts = document.querySelectorAll(".alert-dismissible");
  alerts.forEach(function (alert) {
    setTimeout(function () {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
      if (bsAlert) {
        bsAlert.close();
      }
    }, 5000);
  });

  // Mobile sidebar toggle handler
  const sidebarToggle = document.getElementById("sidebarToggle");
  const sidebar = document.getElementById("sidebar");
  if (sidebarToggle && sidebar) {
    sidebarToggle.addEventListener("click", function () {
      sidebar.classList.toggle("d-none");
    });
  }
});

