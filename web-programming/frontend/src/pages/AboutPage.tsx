export default function AboutPage() {
  return (
    <div className="page" style={{ maxWidth: 720 }}>
      <div className="page-header">
        <div>
          <h2 className="page-title">About Us</h2>
          <p className="page-subtitle">Who we are and what we do</p>
        </div>
      </div>

      {/* Mission */}
      <div className="card" style={{ marginBottom: 20 }}>
        <h3 style={{ marginBottom: 12 }}>Our Mission</h3>
        <p style={{ lineHeight: 1.7, color: "var(--text-muted)" }}>
          At <strong style={{ color: "var(--text)" }}>NucleiAI</strong>, we believe that breakthroughs
          in biomedical research should not be slowed down by manual, error-prone processes.
          Our mission is to accelerate scientific discovery by replacing tedious cell counting
          with fast, accurate, and reproducible AI-powered analysis — giving researchers more
          time to focus on what matters: the science.
        </p>
      </div>

      {/* What we do */}
      <div className="card" style={{ marginBottom: 20 }}>
        <h3 style={{ marginBottom: 12 }}>What We Do</h3>
        <p style={{ lineHeight: 1.7, color: "var(--text-muted)", marginBottom: 16 }}>
          NucleiAI is an AI-powered microscopy analysis platform that automatically segments
          and counts cell nuclei in histopathology images. A researcher simply uploads a
          microscopy image and within seconds receives:
        </p>
        <ul style={{ lineHeight: 2, paddingLeft: 20, color: "var(--text-muted)" }}>
          <li>A precise cell nucleus count</li>
          <li>A segmentation mask highlighting each detected nucleus</li>
          <li>A colour-coded overlay visualisation</li>
          <li>A full analysis history exportable as CSV</li>
        </ul>
        <p style={{ lineHeight: 1.7, color: "var(--text-muted)", marginTop: 16 }}>
          Our platform is powered by a custom-trained <strong style={{ color: "var(--text)" }}>U-Net deep learning model</strong> built
          on a ResNet-18 encoder, trained on annotated histopathology datasets with ground-truth
          XML annotations. The result is a model that consistently outperforms traditional
          threshold-based methods in both accuracy and robustness.
        </p>
      </div>

      {/* Why unique */}
      <div className="card" style={{ marginBottom: 20 }}>
        <h3 style={{ marginBottom: 12 }}>Why NucleiAI Is Unique</h3>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          {[
            { icon: "⚡", title: "Speed", desc: "Results in under 2 seconds — what used to take a researcher 30 minutes now takes a machine 2 seconds." },
            { icon: "🎯", title: "Accuracy", desc: "U-Net segmentation trained on real histopathology data achieves human-level precision on standard benchmarks." },
            { icon: "🔒", title: "Security", desc: "Enterprise-grade security: JWT auth, TOTP 2FA, OAuth, role-based access, rate limiting, and encrypted storage." },
            { icon: "👥", title: "Team Ready", desc: "Multi-user platform with 4-tier roles — managers, admins, researchers, and viewers — all manageable from one dashboard." },
            { icon: "📊", title: "Reproducible", desc: "Every analysis is logged with its exact parameters so results can always be reproduced and audited." },
            { icon: "🌐", title: "Accessible", desc: "Web-based, no installation required. Works from any browser on any device, anywhere in the world." },
          ].map(({ icon, title, desc }) => (
            <div key={title} style={{ background: "var(--surface-2, #1a1a2e)", borderRadius: 10, padding: 16 }}>
              <div style={{ fontSize: 24, marginBottom: 8 }}>{icon}</div>
              <div style={{ fontWeight: 600, marginBottom: 6 }}>{title}</div>
              <div style={{ fontSize: 13, color: "var(--text-muted)", lineHeight: 1.6 }}>{desc}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
