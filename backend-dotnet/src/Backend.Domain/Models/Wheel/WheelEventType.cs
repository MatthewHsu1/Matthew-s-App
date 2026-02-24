using System.ComponentModel.DataAnnotations;

namespace Backend.Domain.Models.Wheel
{
    public enum WheelEventType
    {
        [Display(Name = "State initialized")]
        StateInitialized = 0,

        [Display(Name = "Option opened")]
        OptionOpened = 1,

        [Display(Name = "Option closed")]
        OptionClosed = 2,

        [Display(Name = "Expired")]
        Expired = 3,

        [Display(Name = "Assigned")]
        Assigned = 4,

        [Display(Name = "Shares updated")]
        SharesUpdated = 5,

        [Display(Name = "Reconciled")]
        Reconciled = 6
    }
}
