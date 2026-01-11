document.addEventListener('DOMContentLoaded', () => {
    console.log('ArchAI Dashboard Initialized');

    // Initialize Lucide icons (already done in index.html, but safe here too)
    if (window.lucide) {
        window.lucide.createIcons();
    }

    // Mock data update simulation
    const riskMeter = document.getElementById('riskMeter');
    const healthStatus = document.querySelector('.health-status');
    const alertTower = document.getElementById('alertTower');

    // Check for auth success in URL
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('auth') === 'success') {
        const loginModal = document.getElementById('loginModal');
        if (loginModal) loginModal.style.display = 'none';
        createAlert('Authentication successful. Your architectural lab is now active.', 'critical');
    }

    // Backup Button Logic
    const backupBtn = document.getElementById('backupBtn');
    if (backupBtn) {
        backupBtn.addEventListener('click', () => {
            createAlert('Initiating encrypted backup to Google Drive...', 'critical');
            // Simulate encryption and upload
            setTimeout(() => {
                createAlert('Backup successful! Project state encrypted and stored in appDataFolder.', 'critical');
            }, 2000);
        });
    }

    // Animate risk meter on load
    setTimeout(() => {
        if (riskMeter) riskMeter.style.width = '72%';
    }, 500);

    // Dynamic Alert System
    const createAlert = (message, type = 'critical') => {
        const alert = document.createElement('div');
        alert.className = `alert-item glass alert-${type}`;
        alert.innerHTML = `
            <i data-lucide="bell" style="width: 18px; height: 18px;"></i>
            <div>
                <p style="font-weight: 600; font-size: 14px;">Structural Alert</p>
                <p style="font-size: 12px; opacity: 0.8;">${message}</p>
            </div>
        `;
        alertTower.appendChild(alert);
        window.lucide.createIcons();

        // Remove alert after 5 seconds
        setTimeout(() => {
            alert.style.opacity = '0';
            alert.style.transform = 'translateX(120%)';
            setTimeout(() => alert.remove(), 400);
        }, 5000);
    };

    // Simulate real-time alerts
    setTimeout(() => {
        createAlert('Blueprint Task "Refactor Secret Store" flagged as HIGH RISK by CIRAS.', 'critical');
    }, 2000);

    setTimeout(() => {
        createAlert('Stability index decreased on module "graph_engine.py".', 'critical');
    }, 8000);

    // Interactive Drill-Downs for Task Beams
    document.querySelectorAll('.task-beam').forEach(beam => {
        beam.style.cursor = 'pointer';
        beam.addEventListener('mouseenter', () => {
            beam.style.background = 'rgba(255, 255, 255, 0.05)';
        });
        beam.addEventListener('mouseleave', () => {
            beam.style.background = 'none';
        });
        beam.addEventListener('click', () => {
            const taskName = beam.querySelector('span').innerText;
            createAlert(`Viewing architectural details for: ${taskName}`, 'critical');
        });
    });

    // Health Index Pulse
    let health = 84.2;
    setInterval(() => {
        if (healthStatus) {
            const shift = (Math.random() - 0.5) * 0.4;
            health = (health + shift).toFixed(1);
            healthStatus.innerText = health;

            // Subtle color change based on health
            if (health < 80) healthStatus.style.color = 'var(--warning)';
            else healthStatus.style.color = 'var(--success)';
        }
    }, 3000);
});
