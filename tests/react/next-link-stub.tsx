import type { AnchorHTMLAttributes, ReactNode } from 'react';

// Minimal stand-in for next/link: tests only need an anchor.
export default function Link({
  href,
  children,
  ...rest
}: {
  href: string;
  children?: ReactNode;
} & AnchorHTMLAttributes<HTMLAnchorElement>) {
  return (
    <a href={href} {...rest}>
      {children}
    </a>
  );
}
