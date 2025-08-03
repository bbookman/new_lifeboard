import { useState } from 'react';
import { SectionHeader } from './SectionHeader';

interface SettingSection {
  id: string;
  title: string;
  description: string;
  settings: Setting[];
}

interface Setting {
  id: string;
  label: string;
  description?: string;
  type: 'toggle' | 'select' | 'text' | 'number';
  value: any;
  options?: { label: string; value: any }[];
}

export const SettingsView = () => {
  const [settings, setSettings] = useState<SettingSection[]>([
    {
      id: 'data-sources',
      title: 'Data Sources',
      description: 'Configure which data sources to sync and how often',
      settings: [
        {
          id: 'limitless-sync',
          label: 'Limitless AI Sync',
          description: 'Sync conversations and activities from Limitless AI',
          type: 'toggle',
          value: true
        },
        {
          id: 'sync-frequency',
          label: 'Sync Frequency',
          description: 'How often to check for new data',
          type: 'select',
          value: '3-hours',
          options: [
            { label: 'Every hour', value: '1-hour' },
            { label: 'Every 3 hours', value: '3-hours' },
            { label: 'Every 6 hours', value: '6-hours' },
            { label: 'Daily', value: '24-hours' }
          ]
        },
        {
          id: 'news-sync',
          label: 'News Headlines',
          description: 'Include daily news headlines in your timeline',
          type: 'toggle',
          value: true
        },
        {
          id: 'twitter-sync',
          label: 'Twitter Archive',
          description: 'Sync data from Twitter archive files',
          type: 'toggle',
          value: false
        }
      ]
    },
    {
      id: 'privacy',
      title: 'Privacy & Data',
      description: 'Control how your data is processed and stored',
      settings: [
        {
          id: 'local-processing',
          label: 'Local Processing Only',
          description: 'Process all data locally without sending to external services',
          type: 'toggle',
          value: true
        },
        {
          id: 'data-retention',
          label: 'Data Retention Period',
          description: 'How long to keep processed data',
          type: 'select',
          value: '1-year',
          options: [
            { label: '3 months', value: '3-months' },
            { label: '6 months', value: '6-months' },
            { label: '1 year', value: '1-year' },
            { label: 'Forever', value: 'forever' }
          ]
        },
        {
          id: 'embedding-cache',
          label: 'Clear Embedding Cache',
          description: 'Remove all generated embeddings and regenerate them',
          type: 'toggle',
          value: false
        }
      ]
    },
    {
      id: 'ai-assistant',
      title: 'AI Assistant',
      description: 'Configure your personal AI assistant behavior',
      settings: [
        {
          id: 'conversation-context',
          label: 'Conversation Context Length',
          description: 'How many previous messages to include in responses',
          type: 'number',
          value: 10
        },
        {
          id: 'response-style',
          label: 'Response Style',
          description: 'How the AI should communicate with you',
          type: 'select',
          value: 'conversational',
          options: [
            { label: 'Conversational', value: 'conversational' },
            { label: 'Formal', value: 'formal' },
            { label: 'Brief', value: 'brief' },
            { label: 'Detailed', value: 'detailed' }
          ]
        },
        {
          id: 'proactive-insights',
          label: 'Proactive Insights',
          description: 'Allow AI to suggest insights and connections automatically',
          type: 'toggle',
          value: true
        }
      ]
    },
    {
      id: 'interface',
      title: 'Interface',
      description: 'Customize your Lifeboard experience',
      settings: [
        {
          id: 'theme',
          label: 'Theme',
          description: 'Choose your preferred visual theme',
          type: 'select',
          value: 'newspaper',
          options: [
            { label: 'Newspaper', value: 'newspaper' },
            { label: 'Modern', value: 'modern' },
            { label: 'Minimal', value: 'minimal' }
          ]
        },
        {
          id: 'timezone',
          label: 'Timezone',
          description: 'Your local timezone for date/time display',
          type: 'select',
          value: 'America/New_York',
          options: [
            { label: 'Eastern Time', value: 'America/New_York' },
            { label: 'Central Time', value: 'America/Chicago' },
            { label: 'Mountain Time', value: 'America/Denver' },
            { label: 'Pacific Time', value: 'America/Los_Angeles' },
            { label: 'UTC', value: 'UTC' }
          ]
        },
        {
          id: 'compact-mode',
          label: 'Compact Mode',
          description: 'Show more content in less space',
          type: 'toggle',
          value: false
        }
      ]
    }
  ]);

  const updateSetting = (sectionId: string, settingId: string, newValue: any) => {
    setSettings(prev => prev.map(section => 
      section.id === sectionId 
        ? {
            ...section,
            settings: section.settings.map(setting =>
              setting.id === settingId 
                ? { ...setting, value: newValue }
                : setting
            )
          }
        : section
    ));
  };

  const renderSettingInput = (section: SettingSection, setting: Setting) => {
    switch (setting.type) {
      case 'toggle':
        return (
          <label className="setting-toggle">
            <input
              type="checkbox"
              checked={setting.value}
              onChange={(e) => updateSetting(section.id, setting.id, e.target.checked)}
            />
            <span className="toggle-slider"></span>
          </label>
        );
      
      case 'select':
        return (
          <select
            value={setting.value}
            onChange={(e) => updateSetting(section.id, setting.id, e.target.value)}
            className="setting-select"
          >
            {setting.options?.map(option => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        );
      
      case 'text':
        return (
          <input
            type="text"
            value={setting.value}
            onChange={(e) => updateSetting(section.id, setting.id, e.target.value)}
            className="setting-input"
          />
        );
      
      case 'number':
        return (
          <input
            type="number"
            value={setting.value}
            onChange={(e) => updateSetting(section.id, setting.id, parseInt(e.target.value))}
            className="setting-input"
            min="1"
            max="100"
          />
        );
      
      default:
        return null;
    }
  };

  return (
    <div className="settings-view">
      <SectionHeader 
        title="Configuration Center"
        subtitle="Customize your Lifeboard experience"
        accentColor="border-music-accent"
      />
      
      <div className="settings-sections">
        {settings.map((section) => (
          <div key={section.id} className="card mb-6">
            <div className="card-header">
              <h3 className="card-title">{section.title}</h3>
              <p className="text-muted">{section.description}</p>
            </div>
            <div className="card-content">
              <div className="settings-list">
                {section.settings.map((setting) => (
                  <div key={setting.id} className="setting-item">
                    <div className="setting-info">
                      <div className="setting-label">{setting.label}</div>
                      {setting.description && (
                        <div className="setting-description">{setting.description}</div>
                      )}
                    </div>
                    <div className="setting-control">
                      {renderSettingInput(section, setting)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>
      
      {/* Action Buttons */}
      <div className="settings-actions">
        <div className="card">
          <div className="card-content">
            <div className="flex gap-4">
              <button className="button button-primary">
                Save Settings
              </button>
              <button className="button button-outline">
                Reset to Defaults
              </button>
              <button className="button button-outline">
                Export Configuration
              </button>
            </div>
          </div>
        </div>
      </div>
      
      {/* System Information */}
      <div className="mt-6">
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">System Information</h3>
          </div>
          <div className="card-content">
            <div className="system-info">
              <div className="info-item">
                <span className="info-label">Version</span>
                <span className="info-value">1.0.0</span>
              </div>
              <div className="info-item">
                <span className="info-label">Database Size</span>
                <span className="info-value">42.7 MB</span>
              </div>
              <div className="info-item">
                <span className="info-label">Total Items</span>
                <span className="info-value">1,017</span>
              </div>
              <div className="info-item">
                <span className="info-label">Last Sync</span>
                <span className="info-value">2 minutes ago</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};