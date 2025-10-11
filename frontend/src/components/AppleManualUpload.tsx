import { useRef, useState } from 'react';

export const AppleManualUpload = () => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [processing, setProcessing] = useState(false);
  const [uploadMessage, setUploadMessage] = useState('');

  const handleButtonClick = () => {
    fileInputRef.current?.click();
  };

  const handleDirectoryChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) {
      return;
    }

    setProcessing(true);
    setUploadMessage('Processing Apple Music files...');

    const formData = new FormData();
    // Add all files from the selected directory
    for (let i = 0; i < files.length; i++) {
      formData.append('files', files[i]);
    }

    try {
      const response = await fetch('/api/settings/process/apple', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        if (response.status === 404) {
          setUploadMessage('Processing endpoint not found. Please check server configuration.');
        } else {
          const errorData = await response.json().catch(() => ({}));
          setUploadMessage(errorData.detail || `Processing failed with status: ${response.status}`);
        }
        return;
      }

      let result;
      try {
        result = await response.json();
      } catch (jsonError) {
        console.error('Failed to parse response as JSON:', jsonError);
        setUploadMessage('Server response was not valid JSON. Processing may have succeeded.');
        return;
      }

      setUploadMessage(result.message || 'Processing successful!');
    } catch (error) {
      console.error('Error processing directory:', error);
      if (error instanceof TypeError && error.message.includes('fetch')) {
        setUploadMessage('Failed to connect to server. Please check if the backend is running.');
      } else {
        setUploadMessage('An error occurred during processing.');
      }
    } finally {
      setProcessing(false);
      // Reset the file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  return (
    <div>
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleDirectoryChange}
        style={{ display: 'none' }}
        // @ts-ignore - webkitdirectory is not in TypeScript types but is supported
        webkitdirectory=""
        directory=""
        multiple
      />
      <button
        className="button button-primary"
        onClick={handleButtonClick}
        disabled={processing}
      >
        {processing ? 'Processing...' : 'Read directory'}
      </button>
      {uploadMessage && <p className="text-muted mt-2">{uploadMessage}</p>}
    </div>
  );
};
