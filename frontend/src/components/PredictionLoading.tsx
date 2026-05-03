"use client";

export function PredictionLoading({
  title = "Chargement des prédictions",
  subtitle = "Les analyses arrivent dans quelques instants.",
  rows = 3,
}: {
  title?: string;
  subtitle?: string;
  rows?: number;
}) {
  return (
    <div className="prediction-loading fade-up" role="status" aria-live="polite">
      <div className="prediction-loading-head">
        <span className="prediction-loading-spinner" aria-hidden="true" />
        <div>
          <div className="prediction-loading-title">{title}</div>
          <div className="prediction-loading-subtitle">{subtitle}</div>
        </div>
      </div>

      <div className="prediction-loading-list" aria-hidden="true">
        {Array.from({ length: rows }).map((_, index) => (
          <div key={index} className="prediction-loading-row" style={{ animationDelay: `${index * 0.12}s` }}>
            <div className="prediction-loading-logo" />
            <div className="prediction-loading-lines">
              <div className="prediction-loading-line wide" />
              <div className="prediction-loading-line narrow" />
            </div>
            <div className="prediction-loading-bars">
              <div className="prediction-loading-bar" />
              <div className="prediction-loading-bar" />
              <div className="prediction-loading-bar" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
