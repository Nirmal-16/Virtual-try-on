import { Loader2 } from "lucide-react";
import { imageUrl } from "../../api/client";

interface Props {
  tryonUrl: string | null;
  processing: boolean;
}

export function TryOnPreview({ tryonUrl, processing }: Props) {
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-sm font-semibold text-gray-700">Try-On Result</h3>
      <div className="rounded-xl border border-gray-200 bg-gray-50 overflow-hidden aspect-[3/4] flex items-center justify-center">
        {tryonUrl ? (
          <img
            src={imageUrl(tryonUrl)}
            alt="Virtual try-on result"
            className="w-full h-full object-cover"
          />
        ) : processing ? (
          <div className="flex flex-col items-center gap-3 text-gray-400">
            <Loader2 size={32} className="animate-spin text-rose-400" />
            <span className="text-sm">Running virtual try-on…</span>
          </div>
        ) : (
          <span className="text-sm text-gray-400">Awaiting try-on</span>
        )}
      </div>
    </div>
  );
}
