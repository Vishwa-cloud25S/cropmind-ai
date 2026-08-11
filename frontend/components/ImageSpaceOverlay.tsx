import { normalizedRingCentroid, normalizedRingToSvgPoints } from "@/lib/geo";
import AuthedImage from "@/components/AuthedImage";

export interface OverlayPolygon {
  ring: number[][]; // normalized xyxy positions (0..1), closed or open
  color: string; // stroke/fill hex — caller maps risk level
  label?: string;
}

/**
 * Evidence-space overlay: draws zone/region polygons on the stored image at their
 * TRUE coordinates (normalized image space). This is the honest alternative to
 * putting unlocated observations on a geographic map — the image is the space the
 * model actually reasoned in. Pure SVG; coordinates stay exactly as stored.
 */
export default function ImageSpaceOverlay({
  imageUrl,
  imageAlt,
  polygons,
  caption,
}: {
  imageUrl: string;
  imageAlt: string;
  polygons: OverlayPolygon[];
  caption: string;
}) {
  return (
    <figure>
      <div className="relative w-full overflow-hidden rounded-lg border border-stone-200">
        {/* Owner-scoped stored upload — authenticated fetch, honest failure text */}
        <AuthedImage url={imageUrl} alt={imageAlt} className="block w-full" />
        <svg
          viewBox="0 0 1 1"
          preserveAspectRatio="none"
          className="pointer-events-none absolute inset-0 h-full w-full"
          aria-hidden="true"
        >
          {polygons.map((polygon, i) => (
            <polygon
              key={i}
              points={normalizedRingToSvgPoints(polygon.ring)}
              fill={polygon.color}
              fillOpacity={0.18}
              stroke={polygon.color}
              strokeWidth={0.006}
              vectorEffect="non-scaling-stroke"
            />
          ))}
        </svg>
      </div>
      <figcaption className="mt-1 text-xs leading-5 text-stone-500">
        {polygons.map((polygon, i) =>
          polygon.label ? (
            <span key={i} className="mr-3 inline-flex items-center gap-1">
              <span aria-hidden="true" className="inline-block h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: polygon.color }} />
              {polygon.label} (centroid {normalizedRingCentroid(polygon.ring).map((n) => n.toFixed(2)).join(", ")})
            </span>
          ) : null,
        )}
        <span className="block">{caption}</span>
      </figcaption>
    </figure>
  );
}
