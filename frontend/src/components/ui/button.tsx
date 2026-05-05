import React from "react";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: string;
};

export const Button: React.FC<ButtonProps> = ({ children, className = "", variant, ...props }) => {
  const base = className || "px-3 py-1.5 rounded-md";
  return (
    <button {...props} className={base}>
      {children}
    </button>
  );
};

export default Button;
