import { useCallback, useEffect, useState } from "react";
import { format, subDays, addDays, isToday } from 'date-fns';
import { Button } from "./ui/button";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { getTodayYYYYMMDD } from "../lib/utils";

interface DateNavigationProps {
  selectedDate?: string;
  onDateChange?: (date: string) => void;
  isDayViewActive: boolean;
}

export const DateNavigation = ({ selectedDate, onDateChange, isDayViewActive }: DateNavigationProps) => {
  const [displayDate, setDisplayDate] = useState<string>('');
  const [todayDate, setTodayDate] = useState<string>('');

  useEffect(() => {
    const initializeDate = async () => {
      const today = await getTodayYYYYMMDD();
      setTodayDate(today);
      if (selectedDate) {
        setDisplayDate(selectedDate);
      } else {
        setDisplayDate(today);
      }
    };
    initializeDate();
  }, [selectedDate]);

  const handleDateChange = useCallback((date: Date) => {
    const newDate = format(date, 'yyyy-MM-dd');
    setDisplayDate(newDate);
    if (onDateChange) {
      onDateChange(newDate);
    }
  }, [onDateChange]);

  const handlePrevDay = useCallback(() => {
    if (displayDate) {
      const prevDay = subDays(new Date(displayDate + 'T00:00:00'), 1);
      handleDateChange(prevDay);
    }
  }, [displayDate, handleDateChange]);

  const handleNextDay = useCallback(() => {
    if (displayDate) {
      const nextDay = addDays(new Date(displayDate + 'T00:00:00'), 1);
      handleDateChange(nextDay);
    }
  }, [displayDate, handleDateChange]);

  const handleToday = useCallback(() => {
    if (todayDate) {
      handleDateChange(new Date(todayDate + 'T00:00:00'));
    }
  }, [todayDate, handleDateChange]);

  const isDisplayDateToday = displayDate ? isToday(new Date(displayDate + 'T00:00:00')) : false;

  if (!isDayViewActive) {
    return null; // Only render if DayView is active
  }

  return (
    <div className="flex justify-center items-center space-x-2">
      <Button variant="outline" size="icon" onClick={handlePrevDay} aria-label="Previous day">
        <ChevronLeft className="h-4 w-4" />
      </Button>
      <Button variant="outline" onClick={handleToday}>Today</Button>
      {!isDisplayDateToday && (
        <Button variant="outline" size="icon" onClick={handleNextDay} aria-label="Next day">
          <ChevronRight className="h-4 w-4" />
        </Button>
      )}
    </div>
  );
};