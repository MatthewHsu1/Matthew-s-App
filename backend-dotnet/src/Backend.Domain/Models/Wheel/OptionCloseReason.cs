using System.ComponentModel.DataAnnotations;

namespace Backend.Domain.Models.Wheel
{
    public enum OptionCloseReason
    {
        [Display(Name = "Expired")]
        Expired = 0,

        [Display(Name = "Assigned")]
        Assigned = 1,

        [Display(Name = "Manual")]
        Manual = 2,

        [Display(Name = "Unknown")]
        Unknown = 3
    }
}
