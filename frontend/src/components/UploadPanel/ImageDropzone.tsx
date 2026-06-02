import { useCallback, useState } from "react";
import { useDropzone, type FileRejection } from "react-dropzone";
import { Upload, X } from "lucide-react";

const ACCEPTED_TYPES = { "image/jpeg": [], "image/png": [], "image/webp": [] };
const MAX_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB

interface Props {
  label: string;
  file: File | null;
  onFile: (file: File | null) => void;
  disabled?: boolean;
}

export function ImageDropzone({ label, file, onFile, disabled }: Props) {
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback(
    (accepted: File[], rejected: FileRejection[]) => {
      setError(null);
      if (rejected.length > 0) {
        const msg = rejected[0].errors[0]?.message ?? "Invalid file";
        setError(msg);
        return;
      }
      if (accepted.length > 0) {
        onFile(accepted[0]);
      }
    },
    [onFile]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxSize: MAX_SIZE_BYTES,
    maxFiles: 1,
    disabled,
  });

  const preview = file ? URL.createObjectURL(file) : null;

  return (
    <div className="flex flex-col gap-2 w-full">
      <label className="text-sm font-semibold text-gray-700">{label}</label>

      <div
        {...getRootProps()}
        className={`relative border-2 border-dashed rounded-xl flex flex-col items-center justify-center cursor-pointer transition-colors duration-200 overflow-hidden
          ${disabled ? "opacity-50 cursor-not-allowed" : ""}
          ${isDragActive ? "border-rose-400 bg-rose-50" : "border-gray-300 bg-gray-50 hover:border-rose-300 hover:bg-rose-50"}
          ${preview ? "h-56" : "h-44"}
        `}
      >
        <input {...getInputProps()} />

        {preview ? (
          <>
            <img
              src={preview}
              alt="preview"
              className="absolute inset-0 w-full h-full object-cover"
            />
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onFile(null);
                setError(null);
              }}
              className="absolute top-2 right-2 bg-white rounded-full p-1 shadow hover:bg-red-50 transition-colors"
            >
              <X size={14} className="text-gray-600" />
            </button>
          </>
        ) : (
          <div className="flex flex-col items-center gap-2 p-4 text-center">
            <Upload size={28} className="text-gray-400" />
            <p className="text-sm text-gray-500">
              {isDragActive
                ? "Drop it here"
                : "Drag & drop or click to select"}
            </p>
            <p className="text-xs text-gray-400">JPEG, PNG, WebP · max 10 MB</p>
          </div>
        )}
      </div>

      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  );
}
