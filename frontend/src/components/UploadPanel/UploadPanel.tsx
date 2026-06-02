import { useState } from "react";
import { Loader2, Sparkles } from "lucide-react";
import { ImageDropzone } from "./ImageDropzone";

interface Props {
  onUpload: (personFile: File, dressFile: File) => Promise<void>;
  uploading: boolean;
  error: string | null;
}

export function UploadPanel({ onUpload, uploading, error }: Props) {
  const [personFile, setPersonFile] = useState<File | null>(null);
  const [dressFile, setDressFile] = useState<File | null>(null);

  const canSubmit = personFile !== null && dressFile !== null && !uploading;

  const handleSubmit = async () => {
    if (!personFile || !dressFile) return;
    await onUpload(personFile, dressFile);
  };

  return (
    <div className="flex flex-col gap-6 w-full max-w-2xl mx-auto">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <ImageDropzone
          label="Your Photo"
          file={personFile}
          onFile={setPersonFile}
          disabled={uploading}
        />
        <ImageDropzone
          label="Wedding Dress"
          file={dressFile}
          onFile={setDressFile}
          disabled={uploading}
        />
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <button
        type="button"
        onClick={handleSubmit}
        disabled={!canSubmit}
        className="flex items-center justify-center gap-2 w-full py-3 px-6 rounded-xl font-semibold text-white bg-rose-500 hover:bg-rose-600 active:bg-rose-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-200 shadow-md"
      >
        {uploading ? (
          <>
            <Loader2 size={18} className="animate-spin" />
            Uploading…
          </>
        ) : (
          <>
            <Sparkles size={18} />
            Generate Try-On
          </>
        )}
      </button>
    </div>
  );
}
