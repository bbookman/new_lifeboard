import { useRef, useState } from 'react';

export const TwitterManualUpload = () => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState('');

  const handleButtonClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    setUploading(true);
    setUploadMessage('Uploading...');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('/upload/twitter', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        // Handle non-200 responses
        if (response.status === 404) {
          setUploadMessage('Upload endpoint not found. Please check server configuration.');
        } else {
          setUploadMessage(`Upload failed with status: ${response.status}`);
        }
        return;
      }

      let result;
      try {
        result = await response.json();
      } catch (jsonError) {
        console.error('Failed to parse response as JSON:', jsonError);
        setUploadMessage('Server response was not valid JSON. Upload may have succeeded.');
        return;
      }

      setUploadMessage(result.message || 'Upload successful!');
    } catch (error) {
      console.error('Error uploading file:', error);
      if (error instanceof TypeError && error.message.includes('fetch')) {
        setUploadMessage('Failed to connect to server. Please check if the backend is running.');
      } else {
        setUploadMessage('An error occurred during upload.');
      }
    } finally {
      setUploading(false);
      // Reset the file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  return (
    <div>
      <input type="file" ref={fileInputRef} onChange={handleFileChange} style={{ display: 'none' }} accept=".zip" />
      <button className="button button-primary" onClick={handleButtonClick} disabled={uploading}>
        {uploading ? 'Uploading...' : 'Upload'}
      </button>
      {uploadMessage && <p className="text-muted mt-2">{uploadMessage}</p>}
    </div>
  );
};
