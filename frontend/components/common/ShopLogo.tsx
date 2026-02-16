import Image from "next/image";
import { Store } from "lucide-react";

interface ShopLogoProps {
  name: string;
  logoUrl?: string | null;
  size?: "sm" | "md";
}

export default function ShopLogo({ name, logoUrl, size = "sm" }: ShopLogoProps) {
  const sizeClass = {
    sm: "h-5 w-auto",
    md: "h-7 w-auto",
  }[size];

  const textSize = {
    sm: "text-xs",
    md: "text-sm",
  }[size];

  if (logoUrl) {
    return (
      <Image
        src={logoUrl}
        alt={name}
        width={size === "sm" ? 60 : 80}
        height={size === "sm" ? 20 : 28}
        className={sizeClass}
      />
    );
  }

  // Fallback: text badge with icon
  return (
    <div className={`flex items-center gap-1 rounded bg-surface px-2 py-1 ${textSize} font-medium text-gray-300`}>
      <Store className="h-3 w-3" />
      <span>{name}</span>
    </div>
  );
}
