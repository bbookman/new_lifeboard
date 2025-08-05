import { SectionHeader } from './SectionHeader';

export const SettingsView = () => {
  return (
    <div className="settings-view">
      <div className="card mb-6">
        <div className="card-header">
          <h3 className="card-title">Twitter</h3>
        </div>
        <div className="card-content flex items-center justify-between">
          <p className="text-muted">Provide your twitter-x.zip file and import X data</p>
          <button className="button button-primary">Upload</button>
        </div>
      </div>
    </div>
  );
};