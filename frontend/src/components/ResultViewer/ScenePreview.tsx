import { Download, Loader2 } from "lucide-react";
import { imageUrl } from "../../api/client";

interface Props {
  sceneUrl: string | null;
  processing: boolean;
}

export function ScenePreview({ sceneUrl, processing }: Props) {
  const handleDownload = () => {
    if (!sceneUrl) return;
    const a = document.createElement("a");
    a.href = imageUrl(sceneUrl);
    a.download = "wedding_scene.png";
    a.click();
  };

  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-sm font-semibold text-gray-700">Wedding Scene</h3>
      <div className="rounded-xl border border-gray-200 bg-gray-50 overflow-hidden aspect-[3/4] flex items-center justify-center">
        {sceneUrl ? (
          <img
            src={imageUrl(sceneUrl)}
            alt="Indian wedding scene"
            className="w-full h-full object-cover"
          />
        ) : processing ? (
          <div className="flex flex-col items-center gap-3 text-gray-400">
            <Loader2 size={32} className="animate-spin text-rose-400" />
            <span className="text-sm">Generating wedding scene…</span>
          </div>
        ) : (
          <span className="text-sm text-gray-400">Awaiting scene generation</span>
        )}
      </div>

      {sceneUrl && (
        <button
          type="button"
          onClick={handleDownload}
          className="flex items-center justify-center gap-2 w-full py-2.5 px-4 rounded-xl font-semibold text-white bg-rose-500 hover:bg-rose-600 active:bg-rose-700 transition-colors duration-200 shadow-sm text-sm"
        >
          <Download size={16} />
          Download Scene
        </button>
      )}
    </div>
  );
}
