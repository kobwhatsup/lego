import { useState } from 'react';
import { UploadForm } from './components/upload-form.tsx';
import { CreationViewer } from './components/creation-viewer.tsx';
import { Toaster } from './components/ui/toaster';

function App() {
  const [currentVideoId, setCurrentVideoId] = useState<string | null>(null);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b">
        <div className="container mx-auto px-4 py-4">
          <h1 className="text-2xl font-bold">LEGO Creation Viewer</h1>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        {!currentVideoId ? (
          <UploadForm onUploadSuccess={setCurrentVideoId} />
        ) : (
          <CreationViewer videoId={currentVideoId} />
        )}
      </main>

      <Toaster />
    </div>
  );
}

export default App;
