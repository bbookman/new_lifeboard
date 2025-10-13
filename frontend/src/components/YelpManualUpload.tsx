import { useRef, useState } from 'react';

export const YelpManualUpload = () => {
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

    // Look for user_review.html file
    let htmlFile: File | null = null;
    for (let i = 0; i < files.length; i++) {
      if (files[i].name.toLowerCase() === 'user_review.html') {
        htmlFile = files[i];
        break;
      }
    }

    if (!htmlFile) {
      setUploadMessage('Error: user_review.html file not found in selected folder');
      return;
    }

    setProcessing(true);
    setUploadMessage('Processing Yelp reviews...');

    try {
      // Read file content
      const htmlContent = await readFileAsText(htmlFile);

      // Send HTML content to backend
      const response = await fetch('/api/settings/process/yelp', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ html_content: htmlContent }),
      });

      if (!response.ok) {
        if (response.status === 404) {
          setUploadMessage('Processing endpoint not found. Please check server configuration.');
        } else {
          const errorData = await response.json().catch(() => ({}));
          setUploadMessage(errorData.message || `Processing failed with status: ${response.status}`);
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
      console.error('Error processing Yelp file:', error);
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

  const readFileAsText = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const content = e.target?.result;
        if (typeof content === 'string') {
          resolve(content);
        } else {
          reject(new Error('Failed to read file as text'));
        }
      };
      reader.onerror = () => {
        reject(new Error('File reading failed'));
      };
      reader.readAsText(file);
    });
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
