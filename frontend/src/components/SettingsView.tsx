import { TwitterManualUpload } from './TwitterManualUpload';
import { useState, useEffect } from 'react';

interface Prompt {
  id: string;
  title: string;
  document_type: string;
}

interface PromptSelection {
  prompt_document_id: string | null;
  is_active: boolean;
}

export const SettingsView = () => {
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [selectedPromptId, setSelectedPromptId] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'success' | 'error'>('idle');

  // Fetch available prompts on component mount
  useEffect(() => {
    fetchPrompts();
    fetchCurrentSelection();
  }, []);

  const fetchPrompts = async () => {
    try {
      const response = await fetch('/api/documents?document_type=prompt');
      if (response.ok) {
        const data = await response.json();
        setPrompts(data.documents || []);
      }
    } catch (error) {
      console.error('Error fetching prompts:', error);
    }
  };

  const fetchCurrentSelection = async () => {
    try {
      const response = await fetch('/api/settings/prompt-selection');
      if (response.ok) {
        const data: PromptSelection = await response.json();
        setSelectedPromptId(data.prompt_document_id || '');
      }
    } catch (error) {
      console.error('Error fetching prompt selection:', error);
    }
  };

  const handleSavePromptSelection = async () => {
    setLoading(true);
    setSaveStatus('saving');
    
    try {
      const response = await fetch('/api/settings/prompt-selection', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          prompt_document_id: selectedPromptId || null
        }),
      });

      if (response.ok) {
        setSaveStatus('success');
        setTimeout(() => setSaveStatus('idle'), 2000);
      } else {
        setSaveStatus('error');
        setTimeout(() => setSaveStatus('idle'), 3000);
      }
    } catch (error) {
      console.error('Error saving prompt selection:', error);
      setSaveStatus('error');
      setTimeout(() => setSaveStatus('idle'), 3000);
    } finally {
      setLoading(false);
    }
  };

  const getSaveButtonText = () => {
    switch (saveStatus) {
      case 'saving': return 'Saving...';
      case 'success': return 'Saved!';
      case 'error': return 'Error';
      default: return 'Save';
    }
  };

  const getSaveButtonClass = () => {
    const baseClass = "px-4 py-2 rounded font-medium transition-colors ";
    const isDisabled = loading || saveStatus === 'saving' || prompts.length === 0 || selectedPromptId === '';
    
    if (isDisabled) {
      return baseClass + "bg-gray-400 text-white cursor-not-allowed";
    }
    
    switch (saveStatus) {
      case 'success': return baseClass + "bg-green-500 text-white";
      case 'error': return baseClass + "bg-red-500 text-white";
      default: return baseClass + "bg-blue-500 text-white hover:bg-blue-600";
    }
  };

  return (
    <div className="settings-view">
      <div className="card mb-6">
        <div className="card-header">
          <h3 className="card-title">Twitter</h3>
        </div>
        <div className="card-content flex items-center justify-between">
          <p className="text-muted">Provide your twitter-x.zip file and import X data</p>
          <TwitterManualUpload />
        </div>
      </div>

      <div className="card mb-6">
        <div className="card-header">
          <h3 className="card-title">Daily Summary</h3>
        </div>
        <div className="card-content space-y-4">
          <p className="text-muted">Select a prompt to generate daily summaries with AI</p>
          
          <div className="flex flex-col space-y-3">
            <label htmlFor="prompt-select" className="text-sm font-medium">
              Select daily summary prompt:
            </label>
            
            <select
              id="prompt-select"
              value={selectedPromptId}
              onChange={(e) => setSelectedPromptId(e.target.value)}
              className="border border-gray-300 rounded px-3 py-2 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              disabled={loading}
            >
              <option value="">No prompt selected</option>
              {prompts.map((prompt) => (
                <option key={prompt.id} value={prompt.id}>
                  {prompt.title}
                </option>
              ))}
            </select>
            
            <button
              onClick={handleSavePromptSelection}
              disabled={loading || saveStatus === 'saving' || prompts.length === 0 || selectedPromptId === ''}
              className={getSaveButtonClass()}
            >
              {getSaveButtonText()}
            </button>
          </div>
          
          {prompts.length === 0 && (
            <p className="text-sm text-gray-500">
              No prompts available. Create prompts in the Documents section first.
            </p>
          )}
        </div>
      </div>
    </div>
  );
};