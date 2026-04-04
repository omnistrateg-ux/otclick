"use client"

import * as React from "react"
import { cn } from "@/lib/utils"

interface SliderProps extends React.InputHTMLAttributes<HTMLInputElement> {
  value?: number
  onValueChange?: (value: number) => void
}

const Slider = React.forwardRef<HTMLInputElement, SliderProps>(
  ({ className, value, onValueChange, min = 0, max = 100, ...props }, ref) => {
    const percentage = ((Number(value) - Number(min)) / (Number(max) - Number(min))) * 100

    return (
      <div className="relative w-full">
        <input
          type="range"
          ref={ref}
          value={value}
          min={min}
          max={max}
          onChange={(e) => onValueChange?.(Number(e.target.value))}
          className={cn(
            "w-full h-2 bg-zinc-800 rounded-full appearance-none cursor-pointer",
            "[&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-indigo-500 [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:transition-all [&::-webkit-slider-thumb]:hover:bg-indigo-400 [&::-webkit-slider-thumb]:shadow-lg",
            "[&::-moz-range-thumb]:w-5 [&::-moz-range-thumb]:h-5 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-indigo-500 [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:cursor-pointer",
            className
          )}
          style={{
            background: `linear-gradient(to right, #6366f1 0%, #6366f1 ${percentage}%, #27272a ${percentage}%, #27272a 100%)`,
          }}
          {...props}
        />
      </div>
    )
  }
)
Slider.displayName = "Slider"

export { Slider }
