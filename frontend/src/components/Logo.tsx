"use client";

import React from "react";
import Image from "next/image";
import Link from "next/link";
import { useTheme } from "@/context/ThemeContext";

interface LogoProps {
  width?: number;
  height?: number;
  className?: string;
}

const Logo: React.FC<LogoProps> = ({ width = 220, height = 55, className }) => {
  const { mode: theme } = useTheme();

  // Determine which logo to show with cache busting version
  const logoSrc = theme === "dark"
    ? "/assets/logo_dark.png?v=2" 
    : "/assets/logo_clear.png?v=2";

  // Scale up the logo by 15% everywhere
  const finalWidth = width * 1.15;
  const finalHeight = height * 1.15;

  return (
    <Link href="/" className={`flex items-center ${className}`} style={{ textDecoration: 'none', display: 'inline-flex' }}>
      <Image
        src={logoSrc}
        alt="Next-Bet-AI Logo"
        width={finalWidth}
        height={finalHeight}
        priority
        unoptimized
        style={{ objectFit: "contain", cursor: "pointer", transition: "transform 0.2s ease" }}
        onMouseOver={(e) => e.currentTarget.style.transform = 'scale(1.02)'}
        onMouseOut={(e) => e.currentTarget.style.transform = 'scale(1)'}
      />
    </Link>
  );
};

export default Logo;
