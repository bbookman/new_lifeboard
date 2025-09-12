import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from './ui/alert-dialog';

interface SummaryPromptConflictModalProps {
  isOpen: boolean;
  currentPromptTitle: string;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * Modal dialog that appears when user tries to set a prompt as summary
 * but another prompt is already designated as the summary prompt
 */
export const SummaryPromptConflictModal = ({
  isOpen,
  currentPromptTitle,
  onConfirm,
  onCancel
}: SummaryPromptConflictModalProps) => {
  console.log('🟣 SummaryPromptConflictModal rendered with:', {
    isOpen,
    currentPromptTitle,
    onConfirm: !!onConfirm,
    onCancel: !!onCancel
  });

  return (
    <AlertDialog open={isOpen} onOpenChange={(open) => {
      console.log('🟣 AlertDialog onOpenChange:', open);
      !open && onCancel();
    }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Summary Prompt Conflict</AlertDialogTitle>
          <AlertDialogDescription>
            Summary prompt "{currentPromptTitle}" is set. Do you want to make this prompt the summary prompt?
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={() => {
            console.log('🟣 Cancel button clicked');
            onCancel();
          }}>
            No
          </AlertDialogCancel>
          <AlertDialogAction onClick={() => {
            console.log('🟣 Confirm button clicked');
            onConfirm();
          }}>
            Yes
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};