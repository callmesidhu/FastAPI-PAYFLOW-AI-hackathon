import type { FC } from 'react';

export interface WaveDecorationProps {
  position?: 'top-right' | 'bottom-right' | 'bottom-left';
  width?: number;
  height?: number;
  opacity?: number;
}

export const WaveDecoration: FC<WaveDecorationProps> = ({
  position = 'top-right',
  width = 160,
  height = 80,
  opacity = 0.18,
}) => {
  const getPositionStyles = (): React.CSSProperties => {
    switch (position) {
      case 'top-right':
        return { top: 0, right: 0 };
      case 'bottom-right':
        return { bottom: 0, right: 0 };
      case 'bottom-left':
        return { bottom: 0, left: 0 };
    }
  };

  return (
    <div
      aria-hidden="true"
      style={{
        position: 'absolute',
        pointerEvents: 'none',
        opacity,
        ...getPositionStyles(),
      }}
    >
      <svg
        width={width}
        height={height}
        viewBox="0 0 160 80"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="M0 40C30 10 50 70 80 40C110 10 130 70 160 40"
          stroke="var(--color-hairline)"
          strokeWidth="1"
          strokeLinecap="square"
        />
        <path
          d="M0 55C30 25 50 85 80 55C110 25 130 85 160 55"
          stroke="var(--color-hairline)"
          strokeWidth="1"
          strokeLinecap="square"
        />
        <path
          d="M0 25C30 -5 50 55 80 25C110 -5 130 55 160 25"
          stroke="var(--color-hairline)"
          strokeWidth="1"
          strokeLinecap="square"
        />
      </svg>
    </div>
  );
};
